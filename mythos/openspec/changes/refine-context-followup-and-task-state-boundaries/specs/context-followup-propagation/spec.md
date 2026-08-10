## ADDED Requirements

### Requirement: Contexts share a player and execution scope

系统 SHALL 提供统一的 `Context` 基类，所有实际领域 Context SHALL 直接拥有当前 `Player` 和 per-call `ContextScope`。系统 SHALL NOT 要求只承载 `player` 的中间 `PlayerContext` 才能访问玩家。

#### Scenario: Request and command contexts expose the shared player

- **WHEN** Endpoint 创建 RequestContext 或 CommandContext
- **THEN** Context SHALL 直接提供当前 Player，并保留 Request identity 或 request_id 字段

#### Scenario: Task and lifecycle contexts use the same model

- **WHEN** TaskService 或 LifecycleDispatcher 创建 TaskContext 或 PlayerLifecycleContext
- **THEN** Context SHALL 直接提供当前 Player，并可访问当前执行 scope 的 Followup sink

### Requirement: Child contexts reuse the parent execution scope

系统 SHALL 允许 Context 子类通过 `from_context()` 或等价显式构造复用同一个 `ContextScope`。子 Context SHALL NOT 在同一逻辑执行中隐式创建新的 Followup collector。

#### Scenario: Multiple contexts share one sink

- **WHEN** 一个 Endpoint 操作创建 CommandContext、TaskContext 和 ValidationContext
- **THEN** 这些 Context SHALL 写入同一个 Followup sink，Endpoint SHALL 能按产生顺序统一收集它们

#### Scenario: Scope is request-local

- **WHEN** 两个并发请求分别创建 ContextScope
- **THEN** 两个请求的 Followup SHALL 相互隔离，不得写入 Runtime 级或进程全局 collector

### Requirement: Context followups are transport-neutral

统一 Context SHALL 提供 `followup()` 能力，但 Core Followup 类型 SHALL NOT 依赖 FastAPI、HTTP Response 或 ResponseSpec。Followup SHALL 以结构化值在 Core/Domain 层传播。

#### Scenario: Domain context emits a structured followup

- **WHEN** Task、Validation 或 Lifecycle Handler 调用 Context.followup()
- **THEN** Followup SHALL 被加入当前 ContextScope，且 Handler 不需要构造 HTTP Response JSON

#### Scenario: HTTP endpoint serializes followups

- **WHEN** HTTP Endpoint 成功组装 ResponseSpec
- **THEN** Endpoint/Response adapter SHALL 将收集的 Followup 编码为响应 JSON，并执行 JSON object 校验

### Requirement: Non-HTTP workflows can ignore non-persistent followups

系统 SHALL 提供不产生 HTTP 响应的 silent Followup sink。Auth、reconciliation、测试和其他非 HTTP Workflow SHALL 能使用该 sink，而不导入 Endpoint 或 FastAPI。

#### Scenario: Silent workflow emits a followup

- **WHEN** 非 HTTP Workflow 中的 Context 调用 followup()
- **THEN** Followup SHALL 被 NullFollowupSink 忽略，Workflow SHALL 不因缺少 HTTP 响应而失败

#### Scenario: Shared pipeline does not retain request state

- **WHEN** 多个请求复用 Runtime 初始化的 PipelinedTransaction
- **THEN** Pipeline SHALL NOT 保存或复用任一请求的 ContextScope 或 Followup collector
