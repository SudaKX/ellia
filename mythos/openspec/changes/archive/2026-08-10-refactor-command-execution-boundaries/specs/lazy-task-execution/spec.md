## MODIFIED Requirements

### Requirement: Lazy execution occurs at accepted player activity points

系统 SHALL 在玩家注册或 Construct 激活、登录、已认证写命令开始前和显式任务处理请求中触发玩家任务处理。普通已认证写命令 SHALL 使用默认 `EndpointCommandExecutor` 的 Task pre-activity phase；纯读取端点 SHALL NOT 因读取而隐式写入任务状态。内部 Workflow 可以在自己的外层 transaction 中显式调用 TaskService.run_itx()。

#### Scenario: 写命令触发默认任务处理

- **WHEN** 已认证玩家提交一个由 `EndpointCommandExecutor` 执行的写命令
- **THEN** 系统 SHALL 在业务 Operation transaction 前提交该玩家的 Task transaction

#### Scenario: 登录触发任务处理

- **WHEN** 玩家成功完成登录流程
- **THEN** Auth Workflow SHALL 在其认证 transaction 内处理该玩家已经存在的任务；Construct 新增的任务默认可延迟到后续触发点

#### Scenario: 内部 Workflow 显式触发任务处理

- **WHEN** Auth Workflow 或其他受控内部 Workflow 需要在已有 transaction 中处理任务
- **THEN** Workflow SHALL 直接调用 TaskService 的事务内 `run_itx()` 入口，不得依赖 HTTP `EndpointCommandExecutor`

#### Scenario: 读取端点不触发任务写入

- **WHEN** 玩家访问普通读取端点
- **THEN** 系统 SHALL 只读取当前状态，不得隐式创建、更新或删除玩家任务行

### Requirement: Task and Operation transactions are separate

系统 SHALL 提供默认的 `EndpointCommandExecutor` 命令入口，在一次 Request-ID 幂等生命周期内先执行并提交 Task transaction，再执行并提交 Operation transaction。Operation transaction SHALL 重新加载 Player。Operation 失败 SHALL NOT 回滚已经提交的 Task transaction。仅内部补偿或明确不需要任务的 Endpoint 命令可以显式关闭 Task phase。

#### Scenario: Task transaction and Operation transaction both succeed

- **WHEN** Task phase 和业务 Operation 均成功
- **THEN** 系统 SHALL 缓存并返回 Operation 的最终响应

#### Scenario: Operation failure preserves the task transaction

- **WHEN** Task transaction 已提交但 Operation transaction 失败
- **THEN** 系统 SHALL 回滚 Operation 变更，保留 Task transaction 的状态，并释放 Request-ID 缓存占位

#### Scenario: Request-ID replay does not rerun the task phase

- **WHEN** 客户端使用已经完成的 Request-ID 重试同一个写命令
- **THEN** 系统 SHALL 在启动 Task transaction 前返回缓存响应，不得再次执行 Task Handler

### Requirement: Task HTTP endpoints expose semantic operations

系统 SHALL 暴露固定的玩家任务读取和显式处理接口：`GET /api/v1/tasks` 与 `POST /api/v1/tasks/process`。处理接口 SHALL 要求 Bearer JWT 和 UUID `Request-ID`，并 SHALL 使用 Task 专用命令适配器和 Task transaction。处理报告 SHALL 为本轮每个任务返回 `success` 或 `failure` 状态。系统 SHALL NOT 暴露任意任务身份到 Handler Callback 的通用执行路由。

#### Scenario: 查询任务状态

- **WHEN** 已认证玩家请求 `GET /api/v1/tasks`
- **THEN** API SHALL 返回该玩家已激活任务的时间、错误次数和 meta 可公开状态，不得执行任务

#### Scenario: 显式处理任务

- **WHEN** 已认证玩家使用新的 Request-ID 请求 `POST /api/v1/tasks/process`
- **THEN** Task command adapter SHALL 在 Task transaction 中处理该玩家任务，并为每个任务返回成功或失败状态

#### Scenario: 拒绝任意 Callback 路由

- **WHEN** 客户端尝试通过任务身份直接调用 Handler
- **THEN** 系统 SHALL 不提供该通用路由
