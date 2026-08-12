## Context

原始实现把请求级命令、玩家 ORM 状态加载、事务管理、Request-ID 缓存、pre-commit Hook 和惰性 Task 编排集中在 `core/commands/executor.py`。普通写 Router 调用 `execute_with_task()`，任务执行逻辑还维护一套玩家锁定和加载逻辑；AuthService 与启动 reconciliation 则通过 `execute_nocache*()` 复用其中一部分能力。基础迁移完成后，仍需进一步减少无行为的包装和重复的执行器装配。

这种结构把 HTTP 命令语义和非 HTTP Workflow 混在一起，也使未来 AchievementChecker 很难同时复用普通命令、Task、Auth 和补偿入口的事务边界。需要将原生 Session transaction 与 PlayerLoader 作为应用基础设施，将 `EndpointCommandExecutor` 限定为 HTTP 适配层，将包含任务领域执行能力的 TaskService、AchievementChecker 等对象保留为不拥有外层事务的事务内 Service。

系统仍需遵守以下约束：Registry 在启动期冻结为只读 Catalog；PlayerInterface 写入只能发生在受控 transaction 中；模块不能提交 Session 或新增通用 Callback HTTP 路由；现有 `/api/v1` 路由语义和 Request-ID 协议保持不变。

## Goals / Non-Goals

**Goals:**

- 将 `core/commands` 移到独立的顶层 `mythos.commands` 边界。
- 提供可复用的 RequestCache lease、原生 `AsyncSession.begin()`、PlayerLoader 和有限的单 transaction Pipeline 基础设施。
- 让普通 Endpoint Command 默认执行 Task 前置阶段，并保留后续 Achievement 检查和 effect 的接入位置。
- 将 Task-only HTTP 命令从普通 Player Operation Executor 中分离。
- 让 TaskService、AchievementChecker 和其他 Domain Service 只修改当前 Player/Interface 状态，不拥有外层 commit/rollback。
- 将 Router 统一迁移到 `endpoints` 子包，建立 `endpoints -> commands/services` 的依赖方向。
- 让 Auth Workflow 和 reconciliation 在不依赖 `EndpointCommandExecutor` 的情况下复用相同的事务和 Player 加载基础设施。
- 保持外部 HTTP 路径、认证方式、Request-ID 格式和 Task 的独立 Task/Operation transaction 语义。

**Non-Goals:**

- 本变更不实现 AchievementRegistry、AchievementInterface、成就持久化表或具体成就 condition/effect。
- 本变更不引入后台 Task 调度器、消息队列或 Outbox。
- 本变更不改变 TaskHandler 的 `TaskContext`、savepoint、exception 或 `time_1/time_2/meta` 语义。
- 本变更不把所有 Service 改造成无 Session 的纯函数；Auth Workflow 和 reconciliation 仍可拥有自己的外层事务。
- 本变更不改变公共 API URL 或提供通用 Handler Callback 路由。

## Decisions

### 1. 将 commands 移出 core

新增顶层 `mythos.commands` 包。`core` 保留配置、数据库、异常和运行时基础对象；commands/application 层可以依赖 persistence、players 和 services，但不能被领域 Service 反向依赖。

推荐依赖方向：

```text
endpoints -> EndpointCommandExecutor -> commands infrastructure
endpoints -> Domain Services
workflows -> session.begin() + PlayerLoader + Domain Services
Domain Services -> Player / PlayerInterface / frozen Catalog
```

`EndpointCommandExecutor` 不应被 AuthService、TaskService 或 reconciliation 导入。

备选方案是保留 `core.commands`，但这会继续把应用层 ORM 和 HTTP 命令概念放进 core，边界问题不会消失，因此不采用。

### 2. RequestCache 独立于事务和 Player

`RequestCache` 只负责 Request-ID 的 reserve、重放、进行中冲突、跨玩家拒绝、release 和 complete。它不创建 Session、不锁 Player、不执行 Operation。

RequestCache 提供一个同步 `with` lease。Lease 获取时完成 reserve；如果 block 内异常退出且没有调用 `complete()`，lease 自动 release；如果命中已完成响应，lease 直接暴露 replay response，不执行 block 内的领域操作。RequestCache 本身不需要 async context manager，因为 reserve/release/complete 都是进程内同步操作。

Request-ID 的一次逻辑生命周期可以包含多个物理 transaction。普通带 Task 命令仍先提交 Task transaction，再执行 Operation transaction；两个阶段共享同一个 RequestCache lease。

这样 Task-only 命令、Achievement compensation 命令和普通 Player 命令都能复用 Request-ID 机制，而不会让 RequestCache 依赖某个领域 Executor。

请求级 Endpoint pipeline 可以使用以下结构，异常路径由 lease 自动清理：

```python
with request_cache.lease(request_id, player_id) as lease:
    if lease.replay is not None:
        return lease.replay
     async with session.begin():
        response = await operation()
    lease.complete(response)
    return response
```

### 3. 原生 Session transaction 与 PlayerLoader 分离

commands 基础设施不再提供 `transaction_scope()` 包装。所有拥有 transaction 的调用方直接使用 `async with session.begin()`；SQLAlchemy 原生上下文负责正常退出提交、异常退出回滚。

已有外层 transaction 的 Workflow 直接在当前 `session.begin()` scope 内调用事务中 Service。`run_itx()` 只表示 Service 参与当前 transaction，不得隐式开启、提交或回滚 transaction。

`PlayerLoader` 负责：

- 锁定 `PlayerRecord` 行并在玩家不存在时报告错误。
- 创建 writable/read-only Player。
- 根据调用方给出的 `PlayerInterfaces` 加载 Interface。
- 复用同一 transaction 内的 Player 重载逻辑。

PlayerLoader 不决定调用方是否应该运行 Task 或 Achievement Pipeline；它只提供当前玩家的事务状态。PlayerLoader 保留 PlayerRecord 行锁，因为行锁是 Session/持久化并发控制，不是 Player 聚合的领域行为。PlayerLoader 不实现 `__aenter__`/`__aexit__`，因为它不拥有 AsyncSession、transaction 或 commit/rollback 生命周期。

将现有命令执行器和任务执行逻辑中的玩家锁定/加载重复逻辑迁移到 PlayerLoader。PlayerLoader 继续负责 Interface 装配，但不隐式开启 transaction 或提交 Session；它本身也不拥有 transaction 的 commit 或 rollback。

`PlayerInterfaces` 定义在 `players/interfaces/selection.py`，表示 PlayerLoader 和 Player.load_interfaces() 使用的 bitmask。`players/interfaces/__init__.py` SHALL 重新导出 `PlayerInterfaces`，便于调用方使用 `from mythos.players.interfaces import PlayerInterfaces`；内部实现文件可以直接从 `selection` 导入，避免不必要的 package 聚合依赖。`core` 不再定义或 re-export PlayerInterfaces。

### 4. Service 是事务内参与者，不是外层事务拥有者

TaskService、AchievementChecker、ProgressService 等 Service 可以读取 Catalog，并通过当前 Player/PlayerInterface 产生 ORM 变更，但不得自行调用外层 `session.begin()`、`commit()` 或 `rollback()`。TaskService 同时提供任务快照、报告模型和事务内 `run_itx(session, player_id)`；它可以接收调用方的 Session，但不拥有该 Session 的 transaction。

AuthService 在当前设计中是 Auth Workflow：它可以拥有认证 transaction，并在该 transaction 内调用 TaskService、LifecycleDispatcher 和 PlayerLoader。后续可以重命名为 AuthWorkflow，但不要求本变更立即改名。

ReconciliationRunner 同样是 Workflow，负责批量玩家遍历和每个玩家的 transaction；它不能把启动维护误当成普通 Endpoint Command。

### 5. PipelinedTransaction 只抽象单 transaction 内的稳定阶段

新增 `PipelinedTransaction` 只支持有限、可测试的单 transaction 阶段组合：

```text
Player operation / domain service call
  -> optional post-operation phase
  -> ordered pre-commit hooks
  -> transaction completion
```

`PipelinedTransaction` 不拥有 transaction；调用方先使用 `async with session.begin()`，再把当前 `session` 和 `player` 传给 Pipeline。Pipeline operation、post-operation phase 和 pre-commit hook 都直接接收 `(session, player)`，不创建或传递 `PipelineContext`。TaskService 的单个 Handler savepoint 和内部 Handler hooks 仍由 TaskService 管理；Pipeline 不会替代 Task 调度器。

`PipelinedTransaction` 在应用启动期由 Runtime 按固定的 post-operation phases 和 pre-commit hooks 初始化为共享实例。普通 EndpointCommandExecutor 由外层组合多个物理 transaction：Task transaction 由 TaskService 完成，Operation transaction 内再运行共享的 PipelinedTransaction。AchievementChecker 后续可以作为 Operation Pipeline 的 post-operation phase 接入，使业务 Operation 产生的状态与成就 effect 位于同一 Operation transaction 内。

Pipeline 不依赖 FastAPI Router。HTTP followup、ResponseSpec 和 Request-ID 只由 `EndpointCommandExecutor` 适配，内部 Workflow 没有 HTTP 响应时可以不提供这些能力。共享 PipelinedTransaction 必须保持配置不可变；Task Handler 和不适用 hooks 的 reconciliation 显式绕过它。

### 6. EndpointCommandExecutor 只服务于 endpoints

EndpointCommandExecutor 负责：

- Bearer 身份对应的 Request-ID lease。
- CommandContext 创建。
- 普通 Player Operation 的 transaction 编排。
- Task pre-activity phase 的默认接入。
- post-operation Service/Pipeline 阶段。
- ResponseSpec、followups 和 CachedResponse 组装。

`execute_tasks()` 移动为 TaskCommandExecutor 或 Task endpoint 专用适配器。它使用 RequestCache lease 和原生 `session.begin()`，调用 TaskService，但不经过普通 Player Operation Pipeline，也不重复执行 Task phase。`TaskCommandExecutor` 与 `EndpointCommandExecutor` 位于同一个 `commands/executor.py` 模块中。

Auth、reconciliation 和其他内部 Workflow 不导入 EndpointCommandExecutor；它们直接组合原生 `session.begin()`、PlayerLoader 和 Domain Service。

### 7. Router 迁移到 endpoints

将当前 `services/*/router.py` 和 `auth/router.py` 移到 `mythos.endpoints`。Endpoint 只负责 HTTP 参数、鉴权依赖、错误映射和调用 CommandExecutor/Service。

Domain Service 不应返回 HTTP 专用 `ResponseSpec`。在迁移过程中，现有 ValidationService 等返回值可以先保持兼容，随后由 Endpoint 将领域结果映射为 ResponseSpec；该调整不改变 HTTP body。

`main.py` 通过 `mythos.endpoints.router` 或同等聚合入口挂载所有 `/api/v1` Router，避免逐个从 Service 子包导入 Router。

## Risks / Trade-offs

- [风险] 顶层包迁移会造成大量内部 import 变化和潜在循环依赖。→ 先建立 `mythos.commands` 基础层和 import 约束，再迁移 Router；增加架构 import 测试。
- [风险] TaskService 重载 Player 时可能丢失 transaction 内的临时 Handler 状态。→ PlayerLoader 只负责可靠重载；TaskService 继续负责 Handler savepoint 后的上下文丢弃和状态重建。
- [风险] TaskService 同时提供读取和事务内执行能力，可能被误用为外层事务拥有者。→ 保持 `run_itx()` 命名和架构测试，禁止在 TaskService 内进入 `session.begin()`。
- [风险] 共享 PipelinedTransaction 的 hooks 配置可能被不适用的 Workflow 误用。→ Runtime 只提供固定默认 Pipeline；Task Handler 和 reconciliation 不调用它。
- [风险] 默认 Endpoint Command 执行 Task 会增加每个写请求的事务和锁开销。→ 保留 Task-only、内部 no-task Workflow 入口，并让无任务玩家快速完成空 Task phase。
- [风险] Operation 失败后 Task transaction 已提交，Request-ID 释放后重试可能再次运行 Task。→ 保留现有契约并增加测试；后续单独评估持久化幂等记录或 Task Handler 幂等要求。
- [风险] AuthWorkflow 不再使用 `EndpointCommandExecutor` 后，认证、Construct 和 Task 的提交顺序可能改变。→ 迁移时保留单一 Auth 外层 transaction，并增加注册、登录、登出回滚测试。
- [风险] Endpoint followup 不能自然传播到没有 HTTP 响应的内部 Workflow。→ followup 继续由 CommandContext/Endpoint 适配；PipelinedTransaction 只传递 session/player，持久化通知或 Outbox 留待后续变更。
- [风险] 现有 Service 返回 ResponseSpec 会继续污染领域层。→ 先保证行为兼容，再逐步将 Service 返回值改为领域结果，由 endpoints 负责 HTTP 映射。

## Migration Plan

1. 新增 `mythos.commands` 顶层包和最小的 RequestCache lease、PlayerLoader、PipelinedTransaction 类型，不改变现有调用。
2. 将 `CommandTransactionExecutor._load_player()` 和任务执行中的玩家锁逻辑迁移到 PlayerLoader，并为现有行为补充测试。
3. 抽出 `EndpointCommandExecutor`，先以适配器形式复用现有普通命令默认 `execute()` 语义。
4. 将 Task-only 的 `execute_tasks()` 移到 TaskCommandExecutor/Task endpoint 适配器，保留 Request-ID、事务和报告格式。
5. 将任务领域执行能力并入 TaskService；保留不拥有外层 transaction 的 `run_itx()` 入口，并让 Auth、Endpoint 和 Task-only adapter 复用同一个 TaskService。
6. 将所有事务包装替换为调用方直接使用 `async with session.begin()`，保留 PlayerLoader 负责行锁、加载和重载。
7. 将 TransactionPipeline 重命名为 PipelinedTransaction，移除 PipelineContext，所有 operation/phase/hook 直接接收 session/player，并在 Runtime 上初始化共享实例。
8. 将 TaskCommandExecutor 合并到 `commands/executor.py`，同时保留 EndpointCommandExecutor 与 TaskCommandExecutor 两个类的边界。
9. 将各 Router 迁移到 `mythos.endpoints`，由统一 endpoint 聚合器挂载现有 `/api/v1` 路由。
10. 将普通 Endpoint Command 的默认 pipeline 改为 Task phase + Operation，并保留后续 Achievement phase 的扩展点。
11. 删除 `core/commands` 旧实现和过渡导入，更新 ApplicationRuntime、ServiceContainer、文档、AGENTS 约束和全部测试。

回滚时可以先恢复旧 Router import 和旧 CommandTransactionExecutor facade；由于本变更不修改数据库 schema 和 HTTP URL，回滚主要是 Python 包路径、依赖组装和事务调用方式回滚。所有新基础设施在删除旧实现前应通过完整测试。

## Open Questions

- `commands` 顶层包是否同时承载 HTTP ResponseSpec，还是将 ResponseSpec/followup 适配器进一步放到 endpoints。
- 普通 Endpoint Command 的 Achievement post-operation 阶段是否在本变更中只提供接口，还是同时接入一个空的 Pipeline slot。
- Request-ID 在 Task transaction 已提交但 Operation 失败后的重试语义是否继续保持现状。
