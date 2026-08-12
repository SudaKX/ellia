## MODIFIED Requirements

### Requirement: EndpointCommandExecutor owns HTTP command concerns
系统 SHALL 提供只由 `endpoints` 层使用的 `EndpointCommandExecutor`。该 Executor SHALL 负责 Request-ID lease、CommandContext、普通玩家命令 transaction、Operation 提交后的独立 Achievement Check/Effect transaction、HTTP ResponseSpec/CachedResponse 组装、ContextScope 创建和配置的 Pipeline 阶段；Operation 内的领域事件 SHALL 由 endpoint 或其 operation 在同一 transaction 中使用已加载 Player 显式派发。配置 AchievementService 时，Executor SHALL 为 Operation 加载 AchievementInterface，并在 Operation Pipeline 成功后、提交前 drain 主动 grants；Operation 提交后 SHALL 将 drained immediate grants 与 Check candidates 合并为至多一个 Effect batch。Check/Effect 失败 SHALL 以安全 warning 聚合到已完成的 Operation 响应，并 SHALL NOT 回滚 Operation。Domain Service 和内部 Workflow SHALL NOT 依赖 EndpointCommandExecutor。

#### Scenario: Endpoint executes a normal player write command
- **WHEN** Endpoint 调用默认命令执行入口
- **THEN** Executor SHALL 创建 HTTP collecting ContextScope 和可写 CommandContext，执行 Operation，允许 Operation 在提交前同步派发领域事件和主动 grant，drain grants 并提交 Operation transaction，在新的 Check/Effect transaction 中运行 Achievement，聚合安全 warning，将 Context Followup 转换为响应内容，并在全部补偿阶段完成后缓存响应

#### Scenario: Proactive effects use one batch after a successful operation
- **WHEN** 一个成功 Operation 同时产生主动 immediate grants 和 condition immediate candidates
- **THEN** Executor SHALL 在 Operation 提交后按 Catalog 顺序去重这些 candidates，并仅运行一个 Effect transaction

#### Scenario: Failed check does not discard committed proactive grants
- **WHEN** 成功 Operation drain 了主动 immediate grants 且之后 Check transaction 失败
- **THEN** Executor SHALL 保留 check warning，并 SHALL 使用 drained grants 单独启动 Effect transaction；condition candidates SHALL 不得因失败 Check 而进入该 batch

#### Scenario: Internal workflow does not depend on endpoint command execution
- **WHEN** Auth Workflow 执行认证、Construct 或 Task 操作
- **THEN** Workflow SHALL 通过原生 `session.begin()`、PlayerLoader、Domain Service 和同步 EventDispatcher 完成操作，不得导入 EndpointCommandExecutor
