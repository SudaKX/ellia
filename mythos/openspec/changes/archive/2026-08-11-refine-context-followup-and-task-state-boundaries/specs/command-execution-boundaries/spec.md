## MODIFIED Requirements

### Requirement: Domain Services are transaction-neutral

TaskService、AchievementChecker 及其他 Domain Service SHALL 可以在当前 Player 上执行 ORM/PlayerInterface 写操作，但 SHALL NOT 自行管理外层 transaction、Request-ID 缓存、HTTP 响应或 Endpoint 专用 Context。TaskService SHALL 提供事务内 `run_itx(session, player_id, scope)` 入口；scope SHALL 只承载 per-call 的 transport-neutral Followup sink，并 SHALL NOT 要求 HTTP CommandContext。该入口 SHALL 只参与调用方已有 transaction。它们 SHALL 能被 Endpoint Command 和非 HTTP Workflow 复用。

#### Scenario: Service mutation participates in the caller transaction

- **WHEN** Achievement effect 通过 PlayerInterface 修改 credits、artifacts 或 achievement state
- **THEN** 修改 SHALL 属于调用方当前 transaction，并在调用方提交或回滚时一并处理

#### Scenario: Service is reused by an internal workflow

- **WHEN** Auth Workflow 或 reconciliation 调用 TaskService
- **THEN** TaskService SHALL 使用 silent scope 或调用方提供的 transport-neutral scope 执行领域逻辑，而不要求 Request-ID、HTTP CommandContext 或 ResponseSpec

### Requirement: EndpointCommandExecutor owns HTTP command concerns

系统 SHALL 提供只由 `endpoints` 层使用的 `EndpointCommandExecutor`。该 Executor SHALL 负责 Request-ID lease、CommandContext、普通玩家命令 transaction、HTTP ResponseSpec/CachedResponse 组装、ContextScope 创建和配置的 Pipeline 阶段；Domain Service 和内部 Workflow SHALL NOT 依赖它。Endpoint SHALL 负责将 ContextScope 中的 Followup 编码为 HTTP JSON。

#### Scenario: Endpoint executes a normal player write command

- **WHEN** Endpoint 调用默认命令执行入口
- **THEN** Executor SHALL 创建 HTTP collecting ContextScope 和可写 CommandContext，执行 Operation，运行配置阶段和 hooks，将 Context Followup 转换为响应内容，并在 transaction 成功后缓存响应

#### Scenario: Internal workflow does not depend on endpoint command execution

- **WHEN** Auth Workflow 执行认证、Construct 或 Task 操作
- **THEN** Workflow SHALL 通过原生 `session.begin()`、PlayerLoader、silent ContextScope 和 Domain Service 完成操作，不得导入 EndpointCommandExecutor

### Requirement: Routers are isolated under endpoints

系统 SHALL 将 HTTP Router 放在统一的 `endpoints` 子包中。Endpoint SHALL 负责 HTTP 参数解析、鉴权依赖、错误映射、Followup JSON 转换和 Endpoint Command 调用；Domain Service 包 SHALL NOT 注册 HTTP Router、依赖 FastAPI 或组装 ResponseSpec。

#### Scenario: Application mounts endpoint routers through one aggregate

- **WHEN** 应用启动并注册 `/api/v1` 路由
- **THEN** `main.py` SHALL 从 endpoints 聚合入口挂载 Router，且现有外部 URL 保持不变

#### Scenario: Domain service remains framework-independent

- **WHEN** Service 被单元测试或内部 Workflow 调用
- **THEN** Service SHALL 不要求 FastAPI Request、Request-ID、HTTP ResponseSpec 或 Endpoint followup JSON 才能执行领域操作
