## MODIFIED Requirements

### Requirement: Pipeline phases are composable and domain-neutral

系统 SHALL 提供不拥有 transaction 的 `PipelinedTransaction`，至少支持 Player Operation、可选的 post-operation phase 和有序 pre-commit hooks。所有 operation、phase 和 hook SHALL 直接接收当前 `session` 与 `player`，不得创建或传递 `PipelineContext`。Task transaction 的 Player 加载、单个 batch savepoint、Pipeline 执行和失败计数 SHALL 由 EndpointCommandExecutor 或 TaskCommandExecutor 显式编排；跨 Task transaction 与 Operation transaction 的组合 SHALL 由 EndpointCommandExecutor 或明确的内部 Workflow 显式编排。Operation 提交后的 Achievement Check 和 Effect SHALL 使用独立 transaction，且 Pipeline SHALL NOT 暴露任意客户端可调用的 Callback 路由。

#### Scenario: Task phase precedes a normal operation

- **WHEN** EndpointCommandExecutor 执行需要惰性 Task 的普通写命令
- **THEN** Executor SHALL 在业务 Operation transaction 前锁定并加载一次 Player，创建一个 Task batch savepoint，通过 Pipeline 执行 Task phase；Task phase 成功后提交 Task transaction，再在新的 Operation transaction 中重新加载 Player 并调用单 transaction Pipeline

#### Scenario: Auth Workflow does not include Task phase

- **WHEN** Auth Workflow 执行注册、登录、登出或 refresh
- **THEN** Workflow SHALL 不调用 TaskService，不创建 Task batch savepoint；前端可以在认证成功后使用独立 Request-ID 请求 `/api/v1/tasks/process`，登出不得调用该接口

#### Scenario: Achievement phase runs after the operation

- **WHEN** 普通 Operation transaction 成功提交且 Achievement 检查已配置
- **THEN** EndpointCommandExecutor SHALL 在新的 Check transaction 中执行 condition，再在新的 Effect transaction 中执行 effect；Check 或 Effect 失败 SHALL 生成 warning 而不回滚已提交的 Operation

#### Scenario: Runtime reuses one configured pipeline

- **WHEN** 多个 Endpoint Command 在同一个应用 Runtime 中执行
- **THEN** 它们 SHALL 复用 Runtime 初始化的固定 `PipelinedTransaction` 配置，不得在每次调用时重新构造 hooks 或 `PipelineContext`
