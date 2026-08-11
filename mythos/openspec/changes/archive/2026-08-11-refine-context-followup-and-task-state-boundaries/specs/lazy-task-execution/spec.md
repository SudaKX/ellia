## MODIFIED Requirements

### Requirement: TaskContext stages task state changes

TaskService SHALL 使用当前任务行构造继承统一 Context 的 TaskContext，并向 Handler 提供玩家、任务身份、`time_1`、`time_2`、`exception`、解析后的 meta、统一 UTC 当前时间和 per-call ContextScope。TaskContext SHALL 提供设置 `extra_time`、替换或更新 meta、声明本次延后完成以及发出 transport-neutral Followup 的方法。

Handler SHALL 不直接设置 `time_1` 或 `exception`，也不需要返回 TaskResult。Handler 正常返回且未声明延后时，TaskService SHALL 使用 Handler 成功完成时间自动更新 `time_1`。Handler 抛出可识别任务错误时，TaskService SHALL 不推进 `time_1`。

#### Scenario: Handler normal completion updates task state

- **WHEN** Handler 正常返回且未调用延后方法
- **THEN** TaskService SHALL 更新当前任务的 `time_1`，保存 Context 中的 `time_2` 和 meta，并保留当前 ContextScope 中的 Followup

#### Scenario: Handler can emit a followup

- **WHEN** Task Handler 使用 TaskContext 发出结构化 Followup
- **THEN** Followup SHALL 进入当前 per-call ContextScope，且 Handler 不得直接构造 HTTP ResponseSpec

#### Scenario: Handler through Player manages task state

- **WHEN** Handler 调用 `Player.tasks.add_task()` 或 `remove_task()`
- **THEN** 任务增删 SHALL 属于当前 Task transaction；本轮开始后新增的任务 SHALL 不在当前调度遍历中递归执行

### Requirement: Lazy execution occurs at accepted player activity points

系统 SHALL 在玩家注册或 Construct 激活、登录、已认证写命令开始前和显式任务处理请求中触发玩家任务处理。普通已认证写命令 SHALL 使用默认 `EndpointCommandExecutor` 的 Task pre-activity phase；纯读取端点 SHALL NOT 因读取而隐式写入任务状态。内部 Workflow 可以在自己的外层 transaction 中调用 TaskService，并为其提供 silent 或其他 transport-neutral ContextScope。

#### Scenario: Internal workflow uses a non-HTTP scope

- **WHEN** Auth Workflow 或 reconciliation 在已有 transaction 中调用 TaskService
- **THEN** Workflow SHALL 不依赖 HTTP CommandContext，TaskContext SHALL 使用 silent 或调用方提供的 ContextScope

#### Scenario: Read endpoint does not execute tasks

- **WHEN** 玩家访问普通读取端点
- **THEN** 系统 SHALL 只读取当前状态，不得隐式创建、更新或删除玩家任务行

### Requirement: Task HTTP endpoints expose semantic operations

系统 SHALL 暴露固定的玩家任务读取和显式处理接口：`GET /api/v1/tasks` 与 `POST /api/v1/tasks/process`。处理接口 SHALL 要求 Bearer JWT 和 UUID `Request-ID`，并 SHALL 使用 Task 专用命令适配器、Task transaction 和 HTTP collecting ContextScope。处理报告 SHALL 为本轮每个任务返回 `success` 或 `failure` 状态；成功响应可以包含由 TaskContext 发出的 Followup JSON。系统 SHALL NOT 暴露任意任务身份到 Handler Callback 的通用执行路由。

#### Scenario: Explicit task processing converts followups

- **WHEN** 已认证玩家使用新的 Request-ID 请求 `POST /api/v1/tasks/process`，且 Task Handler 发出结构化 Followup
- **THEN** Task command adapter SHALL 在 Task transaction 中处理任务，并将 Followup 转换为响应 JSON

#### Scenario: Non-HTTP task processing ignores best-effort followups

- **WHEN** 非 HTTP Workflow 使用 silent ContextScope 处理玩家任务
- **THEN** TaskService SHALL 完成领域逻辑，且不得要求或生成 HTTP response body

#### Scenario: Reject arbitrary callback routes

- **WHEN** 客户端尝试通过任务身份直接调用 Handler
- **THEN** 系统 SHALL 不提供该通用路由
