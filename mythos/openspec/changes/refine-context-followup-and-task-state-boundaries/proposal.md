## Why

当前只有 `RequestContext`/`CommandContext` 持有 followup collector，Task、Lifecycle 和 Validation Context 无法以统一方式发出应用通知。Validation Handler 还依赖包含 Request-ID、HTTP reject 和响应 followup 的 `CommandContext`，导致 Domain Service 与 Endpoint 语义耦合；同时 TaskService 需要一个明确的 per-call 执行范围来传播 followup，而不能依赖 HTTP 类型。

## What Changes

- 新增统一的 `Context` 基类，让所有 Context 直接拥有 `player` 和 per-call `ContextScope`；移除只承载 `player` 的 `PlayerContext` 中间层。
- 新增 Core Followup 值对象、`FollowupSink`、HTTP collector、静默 sink 和 ContextScope；HTTP 序列化只由 Endpoint/Response adapter 负责，Core 不依赖 FastAPI。
- 允许 Task、Lifecycle、Validation 和普通 Command Context 共享同一个 per-call followup sink；非 HTTP Workflow 使用静默 sink。
- **BREAKING** 将 Validation Handler 从 `(CommandContext, payload)` 迁移为领域中立的 `ValidationContext`，ValidationService 不再要求 Request-ID 或 HTTP ResponseSpec。
- **BREAKING** 移除 Validation 路径上的 `CommandContext.reject(status_code, detail)`；领域 `reject()` 不接受 HTTP status，Endpoint 将 `ValidationRejected` 固定转换为 HTTP `409 Conflict`。
- 让 TaskService 接收 per-call ContextScope，并令 TaskContext 使用该 scope；共享 Runtime Pipeline 不保存请求级状态。
- Endpoint 负责收集 Context 附加的 Followup，并在成功响应中转换为 JSON；非 HTTP 调用直接忽略非持久化 Followup。
- 更新 Example Validation、Task、Lifecycle 及相关测试和架构文档，保持现有 URL、事务所有权、Request-ID replay 和 Task/Operation transaction 语义不变。

## Capabilities

### New Capabilities

- `context-followup-propagation`: 定义统一 Context、ContextScope、Followup sink、HTTP 收集与非 HTTP 静默传播边界。
- `validation-execution-context`: 定义 ValidationContext、领域拒绝、固定 HTTP 409 映射和 ValidationService 的非 HTTP 调用契约。

### Modified Capabilities

- `command-execution-boundaries`: 增加 per-call ContextScope/Followup 传播约束，明确 Domain Service 不接收 CommandContext，Endpoint 负责 Followup JSON 转换。
- `lazy-task-execution`: 让 TaskContext 参与统一 ContextScope，明确 TaskService 在 HTTP 与非 HTTP 调用中的 Followup 传播方式。

## Impact

- 影响 `src/mythos/players/context.py`、`src/mythos/core/followups.py` 及新的 ContextScope/Followup 类型。
- 影响 `src/mythos/commands/executor.py`、`src/mythos/services/tasks/service.py`、`src/mythos/auth/service.py` 和 Lifecycle/Task Context 创建点。
- 影响 `src/mythos/registry/validations/definitions.py`、`src/mythos/services/validations/service.py`、`src/mythos/endpoints/validations.py` 及 Example Validation Handler。
- 影响普通 Endpoint、Task-only Endpoint、Auth Workflow 和 reconciliation 的 Context 组装方式，但不改变它们的事务所有权。
- 需要更新 `CommandContext`、Validation Handler 的调用合同、followup HTTP 序列化测试、非 HTTP 静默调用测试和架构文档。
- 不修改数据库 schema，不引入 Outbox 或其他持久化通知设施，不恢复 `ApplicationRuntime.task_service` 重复字段。
