## Context

Mythos 在 `create_app()` 的 lifespan 中完成 Registry freeze，并将只读 Catalog、全局 Service、PlayerFactory 和 `CommandTransactionExecutor` 组装到 `ApplicationRuntime`。请求中的 Player 是持有当前 AsyncSession 和 ORM Interface 的短生命周期聚合；当前写命令由一个事务包裹，读请求通过只读 Context 加载 Interface。

当前没有时间任务定义、玩家任务状态或常驻调度器。新能力需要支持登录、Construct、已认证写命令和显式处理请求触发的惰性执行，同时遵守模块不能直接访问 Session、写入必须经过命令事务、Registry freeze 后 Catalog 只读等约束。

## Goals / Non-Goals

**Goals:**

- 提供独立于 access rule 的异步 TaskRegistry 装饰器和冻结 TaskCatalog。
- 将任务定义与玩家任务状态分离，玩家任务行只保存 `time_1`、`time_2`、`exception` 和 JSON `meta` 等运行数据。
- 通过 `Player.tasks.add_task()` 和 `remove_task()` 管理指定玩家的已注册任务。
- 在运行时根据当前 Catalog 的 Handler 依赖求并集，只加载一次可复用的 Player Interface。
- 将 Task 事务和业务 Operation 事务分离，并保留一次 Request-ID 幂等生命周期。
- 为每个 Handler 提供保存点回滚；可识别的 Handler 错误增加 `exception`，任务外层事务或基础设施错误直接抛出。
- 使用注册身份集合 Snapshot 清理当前 Catalog 中已经不存在的玩家任务记录。
- 提供玩家任务状态读取和显式任务处理 HTTP 契约。

**Non-Goals:**

- 不在应用进程中启动每秒轮询或常驻 asyncio 调度循环。
- 不实现全局任务、外部 Worker、严格墙上时钟触发或跨玩家批量业务任务。
- 不为玩家任务行持久化 Handler dependencies、revision、Handler 代码或任务调度规则。
- 不提供任意 `task_id` 到 Callback 的通用 HTTP 执行路由。
- 不为 Handler 代码变更提供自动版本迁移；同一注册身份下的 Handler 必须保持既有 `time_1`、`time_2` 和 `meta` 语义兼容。

## Decisions

### 1. TaskRegistry 与运行时身份

TaskRegistry 提供独立于 access rule 的异步 Handler 装饰器。装饰器校验 Handler 为异步函数、参数签名为一个 TaskContext，并保存稳定的任务注册身份及 `PlayerInterfaces` 依赖元数据。依赖不是 access rule 的授权条件，只表示 Handler 运行前必须加载的数据 Interface。

TaskCatalog freeze 后保存 `task_id -> TaskDefinition` 索引。为简化 Snapshot 和玩家状态，任务状态中的 `task_id` 使用 TaskRegistry 的稳定注册身份；若实现内部产生 `handler_id`，它必须作为该稳定身份使用，不再额外保存 revision。Handler 代码在同一身份下更新时，运行时始终调用当前冻结的 Handler。

Task Handler 通过 TaskContext 读取任务状态，并可调用：

- `set_extra_time(value)` 修改数据库 `time_2`；
- `update_meta()` 或 `replace_meta()` 修改任务私有 JSON 状态；
- `defer()` 表示本次没有完成任务，不自动推进 `time_1`；
- `context.player.tasks.add_task()` 或 `remove_task()` 添加、移除任务。

Handler 正常返回时，执行器使用一次统一的 UTC 完成时间自动写入 `time_1`，除非 Context 已标记 `defer()`。Handler 不返回 TaskResult，也不能直接修改 `exception`。

### 2. 玩家任务持久化

新增 `player_task_states` 表，逻辑字段为：

```text
player_id  UUID       PK/FK players.id
task_id    VARCHAR    PK
time_1     DATETIME   nullable
time_2     DATETIME   nullable
exception  INTEGER    non-negative, default 0
meta       TEXT       strict JSON, default '{}'
created_at DATETIME
updated_at DATETIME
```

主键为 `(player_id, task_id)`，并为 `task_id` 增加索引以支持启动期清理。任务行存在即表示任务已激活；`remove_task()` 删除任务行，`add_task()` 只接受当前 TaskCatalog 中存在的身份并保持幂等，不因重复添加而重置状态。

`meta` 在数据库中保存为 JSON 字符串，TaskContext 使用解析后的独立字典。序列化必须拒绝不可编码值、非有限数和超出限制的内容。Handler 异常时丢弃本次 Context 变更；任务成功或通过预期错误结果正常结束时才写回 `meta`。

### 3. 惰性触发与依赖加载

支持以下触发点：

- 注册或 Construct 中显式 `add_task()` 激活任务；新任务默认不会自动添加给全部历史玩家；
- 登录时处理当前玩家已经存在的任务；
- 已认证写命令的 `execute_with_task()` 前置阶段；
- 显式任务处理命令。

纯读取接口不隐式写入任务状态。TaskExecutor 在一个任务阶段开始时读取当前玩家的任务键集合，再从 TaskCatalog 找到每个 Handler 的最新依赖并求并集，加载一个可写 Player。正常 Handler 执行复用该 Player；保存点回滚后必须丢弃可能包含失效 Python 缓存的聚合，重载 Player 后继续处理本轮剩余任务。

本轮任务键集合在开始时固定。Handler 新增的任务不会递归进入本轮；Handler 移除当前任务后，执行器不再回写该任务状态。

### 4. Task 事务、保存点和错误边界

`execute_with_task()` 只调用一次 RequestCache.reserve/complete，但内部顺序执行两个物理事务：

```text
Request-ID reserve
  -> Task transaction
  -> Operation transaction
  -> Request-ID complete
```

Task transaction 锁定玩家行，逐个 Handler 使用 `session.begin_nested()` 创建保存点。可识别的 `TaskHandlerError` 会回滚当前保存点，在外层 Task transaction 中原子增加 `exception`，记录当前任务失败，并重载 Player 后继续处理本轮剩余任务。Handler 正常完成后记录当前任务成功。TaskExecutor SHALL 保留现有 pre-commit hook 支持：成功 Handler 的 PlayerInterface 变更 SHALL 在 Task transaction 内按任务阶段边界刷新 Hook，失败 Handler 不得刷新其失败状态；Hook 产生的 SQL 变更随 Task transaction 提交或回滚。

Task 外层事务、保存点控制、数据库操作、meta 编解码、任务 pre-commit hook 或最终提交失败时，不做复杂补偿，直接回滚并抛出原始异常，Operation transaction 不启动。

Operation transaction 重新加载 Player。它失败时只回滚 Operation 的变更，已经提交的 Task transaction 保留。Task Handler 的外部服务和对象存储副作用不属于 SQL 回滚范围，第一版不承诺 exactly-once。

`execute_nocache_itx()` 被生命周期分发使用时必须能够关闭自动 Task 阶段，避免 Construct Handler 递归触发任务。登录和注册由 AuthService 在其直接事务边界中显式编排任务激活或延后执行。

### 5. Task Snapshot 与启动清理

Task Snapshot 只保存当前有效的注册身份集合及其集合指纹，例如：

```json
{
  "schema_version": 1,
  "registry_version": "tsk1_...",
  "handler_ids": ["example.hourly-credit"]
}
```

Snapshot 不保存 dependencies、revision 或玩家任务状态。可以复用现有 SnapshotStore 的原子 JSON 读写机制，但不必复用包含 definition/version 的完整模板条目模型。

启动 reconciliation 以当前 TaskCatalog 为权威集合，删除数据库中 `task_id` 不在当前集合的任务行。Snapshot 缺失时仍必须执行未知身份清理；当前 Catalog 为空而数据库存在任务时默认阻止应用 ready，避免配置错误造成全量删除。清理事务成功后才写入新 Snapshot。

新增注册身份默认只使任务类型可被 `add_task()` 使用。若未来需要自动绑定历史玩家，必须增加显式的 auto-attach 策略，不能由 Snapshot 新增集合自动推断。

### 6. HTTP 与 Interface

增加固定语义端点：

```text
GET  /api/v1/tasks
POST /api/v1/tasks/process
```

读取端点返回当前玩家任务状态，不触发写入。处理端点使用 Bearer JWT、UUID `Request-ID` 和 `execute_with_task()`，返回本次处理报告。处理报告 SHALL 为每个本轮任务返回 `success` 或 `failure` 状态，并可附带任务身份和错误次数；模块不增加通用 Callback HTTP 路由。

`Player.tasks` 是请求级 Interface，负责任务状态读取、`add_task()`、`remove_task()` 和版本/缓存失效通知；TaskExecutor 负责调用冻结 Catalog Handler，不把 Handler 调用能力直接开放给客户端。

## Risks / Trade-offs

- [风险] 同一注册身份下 Handler 代码或 `meta` 结构发生不兼容变化，系统不会自动检测或迁移。→ Handler 必须保持兼容；破坏性变化通过更换稳定任务身份后重新注册，或提供显式数据迁移。
- [风险] Handler 错误后的保存点回滚可能使 Player 内存缓存与数据库状态不一致。→ 正常路径复用 Player；回滚后重载并继续；无法可靠重载或转移 pre-commit 状态时直接终止 Task 阶段。
- [风险] Task transaction 已提交而 Operation transaction 随后失败，任务副作用不会回滚。→ 只将独立、可重复或不要求与 Operation 原子提交的任务放入前置阶段；强一致业务仍使用单一命令事务。
- [风险] `exception` 在 Task 外层事务失败时可能不增加。→ 将复杂基础设施错误直接抛出并记录日志，不尝试不可靠的二次补偿。
- [风险] 启动时清理未知身份可能误删部署期间尚未加载的任务。→ 当前 Catalog 为空时阻止 ready；多版本部署必须保证 Catalog 兼容或使用单独的启动协调。
- [风险] 每次触发都会遍历当前玩家已添加任务。→ 任务状态只按玩家懒惰创建，并限制单次任务数量/执行预算；不启动全局轮询。
- [风险] 对象存储和外部服务调用不能随 SQL 回滚。→ Handler 第一版只保证数据库事务语义；外部副作用需要显式幂等键或后续 Outbox 能力。

## Migration Plan

1. 新增 `player_task_states` ORM Model 和 Alembic migration，创建 `(player_id, task_id)` 主键、`task_id` 索引、时间字段、错误次数和 JSON `meta`。
2. 在 RegistryBundle、RuntimeCatalogs、PlayerFactory、Player、ServiceContainer 和 ApplicationRuntime 中组装 TaskRegistry/TaskCatalog/TaskExecutor。
3. 增加 Task Snapshot 路径与启动 reconciliation；在正式环境迁移完成后再启用任务表清理。
4. 增加 `execute_with_task()`，先验证 Request-ID，再顺序提交 Task transaction 和 Operation transaction。
5. 为登录、Construct、写命令和显式任务处理接入触发点，并保持纯读取端点不写入。
6. 增加单元、事务、HTTP、并发、Snapshot 清理和错误边界测试，再更新领域文档与 API 契约。

回滚时先停止使用任务触发点，再回退应用版本；如确认没有需要保留的任务状态，可回退 migration 删除 `player_task_states` 和任务 Snapshot。任务 Handler 的数据库修改必须在旧版本仍可读取的范围内发布。

## Open Questions

无。已决定 Handler 错误后重载 Player 并继续本轮任务，处理端点返回逐任务成功/失败状态，Task transaction 保留现有 pre-commit hook 支持。
