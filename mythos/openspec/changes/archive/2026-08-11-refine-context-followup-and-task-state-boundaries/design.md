## Context

当前 `PlayerContext` 只承载 `player`，`RequestContext`/`CommandContext` 额外承载 identity、Request-ID 和 HTTP followup collector；`TaskContext` 与 `PlayerLifecycleContext` 没有统一的 followup 能力。`FollowupCollector` 位于 Core，但直接使用 FastAPI JSON encoder，无法被非 HTTP Domain Context 安全复用。

Validation Handler 目前接收 `CommandContext`，因此可以访问 Request-ID、HTTP status reject 和响应 followup。TaskService 也需要在 HTTP Task phase 与 Auth/reconciliation 等非 HTTP Workflow 中创建 TaskContext，但不能依赖 Endpoint 类型或共享 Runtime 状态。

## Goals / Non-Goals

**Goals:**

- 让所有实际领域 Context 直接拥有 `player` 和 per-call `ContextScope`。
- 通过共享 ContextScope 传播结构化 Followup，并支持 HTTP collecting 与非 HTTP silent 两种执行环境。
- 将 Followup 的收集与 JSON/HTTP 序列化分离。
- 让 ValidationService 和 Validation Handler 不依赖 CommandContext、Request-ID 或 ResponseSpec。
- 将 Validation reject 固定映射为 HTTP `409 Conflict`，禁止 Handler 指定 HTTP status code。
- 让 TaskService 使用调用方提供的 ContextScope 创建 TaskContext，同时保持 Service 不依赖 Endpoint/ FastAPI。

**Non-Goals:**

- 不在本 Change 中实现持久化 Outbox、可靠通知投递或消息队列。
- 不改变数据库 schema、Request-ID replay、Task/Operation transaction 或 Task savepoint 语义。
- 不重新引入 `ApplicationRuntime.task_service` 重复字段。
- 不在本 Change 中修复已归档 Change 的认证锁顺序、TaskInterface pending deletion、TaskContext meta 深拷贝或主 spec 旧名称；这些属于上次 Change 的独立优化项。

## Decisions

### 1. Context 使用统一 Player 字段与 Scope 组合

`Context` 直接拥有 `player` 和 `scope`。`PlayerContext` 不再作为只承载 Player 的中间继承层。Request、Command、Task 和 Lifecycle Context 都继承统一 Context，但 TaskContext 继续保持可变状态。

`ContextScope` 不包含 Player，只包含本次逻辑执行共享的 FollowupSink。它在 Endpoint 或 Workflow 边界创建，子 Context 通过 `from_context()` 或显式 scope 参数复用同一实例。Task phase 发生在 CommandContext 创建前，因此 Endpoint 先创建 scope，再分别创建 TaskContext 和 CommandContext。

为避免 frozen dataclass 与可变 TaskContext 的继承冲突，Context 的共享状态使用组合对象；TaskContext 可以继续使用显式可变构造函数。

### 2. Followup 使用 Core Sink 和 Null Object

Core 提供可变的 `Followup(action, data)`、`FollowupSink`、`FollowupCollector`、`NullFollowupSink` 和 `ContextScope`。Context 只有 `follow(Followup)` 入口；Collector 只负责顺序收集和 checkpoint rollback，不导入 FastAPI。Endpoint/Response adapter 在收集时调用 `Followup.to_json()`，再由 `ResponseSpec` 负责 JSON 校验和响应包装。

HTTP 请求创建 collecting scope，Task、Validation、Lifecycle 和 Command Context 共享该 scope。Auth、reconciliation 和测试使用 silent scope；NullFollowupSink 丢弃非持久化 Followup，避免 Domain Service 依赖 HTTP。

共享的 ContextScope 是请求级状态，不能存放于 ApplicationRuntime 或共享 PipelinedTransaction。必须可靠持久化的领域事件不使用 silent Followup，而应另行建模。

### 3. Validation 使用领域中立 Context

ValidationService.submit() 接收 Player、ValidationAttempt 和 payload，并在内部创建 ValidationContext。Handler 不再接收 CommandContext。ValidationContext 继承统一 Context，提供 Player、Followup 和领域 reject。

`reject(reason, details)` 只抛出 `ValidationRejected`，不接收 status code。Endpoint 将所有 ValidationRejected 固定转换为 HTTP `409 Conflict`；需要 404/422 等其他语义时使用独立异常和 Endpoint 映射，不扩展 reject 的参数。

Validation Handler 的结构化 Followup 先进入 ContextScope，Endpoint 在 ResponseSpec 组装时转换为 HTTP JSON。非 HTTP 调用可以使用 silent scope。

### 4. TaskService 使用 per-call ContextScope

TaskService 不保存 ContextScope，也不保存 FollowupCollector。`run_itx()` 在 HTTP 调用中接收当前 scope，在非 HTTP 调用中使用 silent scope；每个 TaskContext 复用该 scope。每个 Handler 前压入当前 Followup 数量检查点；Handler 或保存点失败时弹出栈顶并截断其后的 Followup，避免回滚状态产生通知。TaskService 仍然只参与调用方已有 transaction，不创建 HTTP Context，也不负责 JSON 序列化。

### 5. Endpoint 负责最终响应转换

EndpointCommandExecutor 和 TaskCommandExecutor 在每个逻辑请求边界创建 collecting scope，并在 Task phase、Operation 和 Context Handler 完成后统一调用 scope 的 `to_json()`。事务或 Pipeline 失败时不完成 Request-ID，也不发送 Followup。

## Risks / Trade-offs

- [Risk] Task/Operation 两个物理 transaction 共享一个内存 Followup scope，Operation 失败时 Task 已提交但 Followup 被丢弃。→ Followup 定义为响应通知而非可靠事件；可靠事件另建 Outbox/持久化设计。
- [Risk] NullFollowupSink 可能隐藏调用方期望的通知。→ 只有非持久化 UI/application Followup 可以静默丢弃；必须处理的事件不得使用 Followup。
- [Risk] Context dataclass 继承和可变 TaskContext 的字段初始化复杂。→ 使用 ContextScope 组合对象和显式 TaskContext 构造函数，增加 scope identity 测试。
- [Risk] Validation Handler 签名是 breaking change。→ 同步 Registry definition、Example Handler、Endpoint adapter 和全部 Validation 测试，禁止保留 HTTP status 参数兼容路径。
- [Risk] Followup JSON 验证从 Core 移到 ResponseSpec 后，内部 Workflow 可能产生不可序列化值。→ HTTP 响应边界由 ResponseSpec 严格验证；silent sink 不承担 HTTP 格式责任。

## Migration Plan

1. 新增 Followup/ContextScope/Null sink 类型，并重构 Context 基类及字段。
2. 将 Endpoint、TaskService、Lifecycle 和 Validation Context 创建点接入 scope；先保持 Endpoint 响应结构不变。
3. 迁移 Validation Handler 和 ValidationService，固定 reject 为 HTTP 409 映射。
4. 将 Followup JSON 编码从 Core 移到 Endpoint adapter，补充 HTTP 与 silent scope 测试。
5. 更新 command/lazy-task delta specs、架构文档和 API 文档。
6. 运行聚焦测试和完整 Mythos 测试目录。

回滚时可以恢复旧的 Context 构造与 Validation Handler 签名；本 Change 不涉及数据库迁移。由于 Handler 签名是 breaking change，回滚必须同时恢复 Registry definition、Example 和 Endpoint adapter。

## Open Questions

- 当前 Followup 是否全部属于 best-effort 响应通知，还是有部分需要后续单独建模为持久化领域事件。
- 是否保留 `Context.from_context()` 作为统一构造约定，还是所有 Context 创建点显式传递 ContextScope。
