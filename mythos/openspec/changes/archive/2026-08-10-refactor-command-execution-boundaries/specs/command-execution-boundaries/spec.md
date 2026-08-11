## ADDED Requirements

### Requirement: Request-ID caching is independent from domain execution

系统 SHALL 提供独立于 Player、Task 和 Achievement 领域逻辑的 Request-ID 缓存组件。该组件 SHALL 负责 reserve、已完成响应重放、请求进行中冲突、跨玩家重放拒绝、release 和 complete，并 SHALL 提供可自动清理异常 lease 的同步上下文管理器；它 SHALL NOT 创建数据库 Session、锁定 Player 或执行领域 Operation。

#### Scenario: Completed request is replayed without executing the operation

- **WHEN** 相同玩家使用已经完成的 Request-ID 再次请求
- **THEN** Request cache SHALL 返回原始 CachedResponse，且不得重新执行 Task、Operation 或 Achievement effect

#### Scenario: Failed request releases its Request-ID lease

- **WHEN** 请求 Pipeline 抛出异常且没有完成响应缓存
- **THEN** Request lease 上下文 SHALL 自动释放进行中状态，使后续请求可以重新尝试

### Requirement: Transaction ownership is explicit

系统 SHALL 要求 transaction 所有者直接使用 `async with session.begin()` 显式进入 transaction。原生 Session context SHALL 在正常退出时提交、异常退出时回滚；已有外层 transaction 的 Workflow SHALL 直接复用当前 Session transaction，而不是调用会隐式开启 transaction 的 Service 方法。Domain Service SHALL NOT 自行提交或回滚其调用方提供的 transaction。

#### Scenario: Workflow owns the transaction

- **WHEN** Workflow 使用 `async with session.begin()` 执行一个 Player mutation
- **THEN** Session context SHALL 开启、提交或回滚 transaction，并在 block 正常退出后完成提交

#### Scenario: Nested workflow reuses an outer transaction

- **WHEN** Auth Workflow 在已有认证 transaction 内调用 TaskService 或其他 Service
- **THEN** 内部执行 SHALL 直接复用当前 transaction，不得开启独立 transaction 或提前提交认证变更

### Requirement: PlayerLoader centralizes locking and loading

系统 SHALL 提供可供 Endpoint、Workflow、TaskService 和 AchievementChecker 复用的 PlayerLoader。它 SHALL 支持锁定 PlayerRecord、加载 writable/read-only Player 和按 PlayerInterfaces 加载状态；它 SHALL NOT 隐式提交或回滚 transaction。Player 聚合 SHALL NOT 直接拥有 PlayerRecord 行锁实现。

#### Scenario: Writable Player is locked before mutable state is loaded

- **WHEN** 可写 Workflow 请求加载玩家状态
- **THEN** PlayerLoader SHALL 在加载可变 Player Interface 前锁定对应 PlayerRecord 行

#### Scenario: Task retry reloads a fresh Player aggregate

- **WHEN** Task Handler savepoint 回滚后需要继续处理后续任务
- **THEN** TaskService SHALL 通过同一 PlayerLoader 重载反映当前 transaction 状态的新 Player

### Requirement: Domain Services are transaction-neutral

TaskService、AchievementChecker 及其他 Domain Service SHALL 可以在当前 Player 上执行 ORM/PlayerInterface 写操作，但 SHALL NOT 自行管理外层 transaction、Request-ID 缓存或 HTTP 响应。TaskService SHALL 提供事务内 `run_itx(session, player_id)`，但该入口 SHALL 只参与调用方已有 transaction。它们 SHALL 能被 Endpoint Command 和非 HTTP Workflow 复用。

#### Scenario: Service mutation participates in the caller transaction

- **WHEN** Achievement effect 通过 PlayerInterface 修改 credits、artifacts 或 achievement state
- **THEN** 修改 SHALL 属于调用方当前 transaction，并在调用方提交或回滚时一并处理

#### Scenario: Service is reused by an internal workflow

- **WHEN** Auth Workflow 或 reconciliation 调用 TaskService
- **THEN** TaskService SHALL 执行领域逻辑而不要求 Request-ID 或 HTTP CommandContext

### Requirement: EndpointCommandExecutor owns HTTP command concerns

系统 SHALL 提供只由 `endpoints` 层使用的 `EndpointCommandExecutor`。该 Executor SHALL 负责 Request-ID lease、CommandContext、普通玩家命令 transaction、HTTP ResponseSpec/CachedResponse 组装和配置的 Pipeline 阶段；Domain Service 和内部 Workflow SHALL NOT 依赖它。

#### Scenario: Endpoint executes a normal player write command

- **WHEN** Endpoint 调用默认命令执行入口
- **THEN** Executor SHALL 创建可写 CommandContext，执行 Operation，运行配置阶段和 hooks，并在 transaction 成功后缓存响应

#### Scenario: Internal workflow does not depend on endpoint command execution

- **WHEN** Auth Workflow 执行认证、Construct 或 Task 操作
- **THEN** Workflow SHALL 通过原生 `session.begin()`、PlayerLoader 和 Domain Service 完成操作，不得导入 EndpointCommandExecutor

### Requirement: Pipeline phases are composable and domain-neutral

系统 SHALL 提供不拥有 transaction 的 `PipelinedTransaction`，至少支持 Player Operation、可选的 post-operation phase 和有序 pre-commit hooks。所有 operation、phase 和 hook SHALL 直接接收当前 `session` 与 `player`，不得创建或传递 `PipelineContext`。跨 Task transaction 与 Operation transaction 的组合 SHALL 由 EndpointCommandExecutor 或内部 Workflow 显式编排。Pipeline SHALL NOT 暴露任意客户端可调用的 Callback 路由。

#### Scenario: Task phase precedes a normal operation

- **WHEN** EndpointCommandExecutor 执行需要惰性 Task 的普通写命令
- **THEN** Executor SHALL 在业务 Operation transaction 前执行并提交 Task phase，再在新的 Operation transaction 中调用单 transaction Pipeline

#### Scenario: Achievement phase runs after the operation

- **WHEN** 后续 AchievementChecker 被配置为 post-operation phase
- **THEN** Checker SHALL 看到当前 Operation 产生的 Player 状态，并在同一 Operation transaction 中执行 effect 和 unlock

#### Scenario: Runtime reuses one configured pipeline

- **WHEN** 多个 Endpoint Command 在同一个应用 Runtime 中执行
- **THEN** 它们 SHALL 复用 Runtime 初始化的固定 `PipelinedTransaction` 配置，不得在每次调用时重新构造 hooks 或 `PipelineContext`

### Requirement: Task-only commands use a domain-specific adapter

系统 SHALL 允许 Task-only HTTP 命令通过 Task 专用命令适配器执行。该适配器 SHALL 复用独立的 Request-ID 和原生 Session transaction 基础设施，调用 TaskService，且 SHALL NOT 伪装成普通 Player Operation 或重复执行 Task phase。

#### Scenario: Explicit task processing returns a task report

- **WHEN** 已认证玩家使用新的 Request-ID 请求 `POST /api/v1/tasks/process`
- **THEN** Task command adapter SHALL 在一个 Task transaction 中运行 TaskService，并返回 TaskRunReport

#### Scenario: Task processing replay is cached

- **WHEN** 客户端重放已经完成的任务处理 Request-ID
- **THEN** 适配器 SHALL 返回原始报告，且不得再次运行 Task Handler

### Requirement: Routers are isolated under endpoints

系统 SHALL 将 HTTP Router 放在统一的 `endpoints` 子包中。Endpoint SHALL 负责 HTTP 参数解析、鉴权依赖、错误映射和 Endpoint Command 调用；Domain Service 包 SHALL NOT 注册 HTTP Router 或依赖 FastAPI。

#### Scenario: Application mounts endpoint routers through one aggregate

- **WHEN** 应用启动并注册 `/api/v1` 路由
- **THEN** `main.py` SHALL 从 endpoints 聚合入口挂载 Router，且现有外部 URL 保持不变

#### Scenario: Domain service remains framework-independent

- **WHEN** Service 被单元测试或内部 Workflow 调用
- **THEN** Service SHALL 不要求 FastAPI Request、Request-ID 或 HTTP ResponseSpec 才能执行领域操作
