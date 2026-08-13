## MODIFIED Requirements

### Requirement: Domain Services are transaction-neutral
TaskService、AchievementService、AccountService 及其他 Domain Service SHALL 可以在当前 Player 上执行 ORM/PlayerInterface 写操作，但 SHALL NOT 自行管理外层 transaction、Request-ID 缓存、HTTP 响应、Player 锁或 Endpoint 专用 Context。TaskService SHALL 提供接收调用方已加载 Player 的批次入口；AchievementService SHALL 提供事务中立的 condition 检查、earned 状态写入和 effect 批次入口；AccountService SHALL 只执行虚拟账号领域操作，不得依赖 EventDispatcher。scope SHALL 只承载 per-call 的 transport-neutral Followup sink，并 SHALL NOT 要求 HTTP CommandContext。Task 批次和 Achievement Check/Effect 的 Pipeline、Player 加载、锁和 transaction SHALL 由 CommandExecutor 或明确的 Workflow 组织；EventBus 的发布 SHALL 由拥有已加载 Player 和 transaction 的 Endpoint 或 Workflow 显式组织。

#### Scenario: Service mutation participates in the caller transaction
- **WHEN** Achievement effect 通过 PlayerInterface 修改 credits、artifacts 或 achievement state
- **THEN** 修改 SHALL 属于调用方当前 transaction，并在调用方提交或回滚时一并处理

#### Scenario: Service is reused by an internal workflow
- **WHEN** 非 Auth 的内部 Workflow 明确调用 TaskService
- **THEN** Workflow SHALL 提供已加载 Player 和 silent 或调用方提供的 transport-neutral scope 执行领域逻辑，而不要求 Request-ID、HTTP CommandContext 或 ResponseSpec；Auth Workflow SHALL 只执行认证、Construct 逻辑和必要的同步事件派发

### Requirement: EndpointCommandExecutor owns HTTP command concerns
系统 SHALL 提供只由 `endpoints` 层使用的 `EndpointCommandExecutor`。该 Executor SHALL 负责 Request-ID lease、CommandContext、普通玩家命令 transaction、Operation 提交后的独立 Achievement Check/Effect transaction、HTTP ResponseSpec/CachedResponse 组装、ContextScope 创建和配置的 Pipeline 阶段；Operation 内的领域事件 SHALL 由 endpoint 或其 operation 在同一 transaction 中使用已加载 Player 显式派发。Check/Effect 失败 SHALL 以安全 warning 聚合到已完成的 Operation 响应，并 SHALL NOT 回滚 Operation。Domain Service 和内部 Workflow SHALL NOT 依赖 EndpointCommandExecutor。

#### Scenario: Endpoint executes a normal player write command
- **WHEN** Endpoint 调用默认命令执行入口
- **THEN** Executor SHALL 创建 HTTP collecting ContextScope 和可写 CommandContext，执行 Operation，允许 Operation 在提交前同步派发领域事件，提交 Operation transaction，在新的 Check/Effect transaction 中运行 Achievement，聚合安全 warning，将 Context Followup 转换为响应内容，并在全部补偿阶段完成后缓存响应

#### Scenario: Internal workflow does not depend on endpoint command execution
- **WHEN** Auth Workflow 执行认证、Construct 或 Task 操作
- **THEN** Workflow SHALL 通过原生 `session.begin()`、PlayerLoader、Domain Service 和同步 EventDispatcher 完成操作，不得导入 EndpointCommandExecutor
