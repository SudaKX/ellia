## ADDED Requirements

### Requirement: TaskRegistry registers asynchronous task handlers

系统 SHALL 提供独立于 access rule 的 TaskRegistry Handler 注册设施。每个任务 SHALL 使用稳定的任务注册身份，并关联一个异步 Handler。Handler SHALL 接收一个 TaskContext 参数；注册时 SHALL 校验其异步性、参数数量、任务身份唯一性和 PlayerInterface 依赖位图。

#### Scenario: 注册有效任务 Handler

- **WHEN** 模块在 Registry freeze 前使用 TaskRegistry 注册一个带稳定身份和合法依赖的异步 Handler
- **THEN** TaskCatalog SHALL 在 freeze 后提供该任务身份到 Handler 定义的索引

#### Scenario: 拒绝 access rule 风格的同步 Handler

- **WHEN** 模块尝试将同步布尔函数注册为任务 Handler
- **THEN** TaskRegistry SHALL 拒绝注册并报告 Handler 签名错误

#### Scenario: 运行时使用当前 Handler 依赖

- **WHEN** TaskExecutor 根据任务身份查找 Handler
- **THEN** TaskExecutor SHALL 从冻结 TaskCatalog 读取该 Handler 当前声明的依赖并用于 Player Interface 加载

### Requirement: Player task state is persisted independently from task definitions

系统 SHALL 使用 `player_task_states` 保存玩家任务运行状态。任务行 SHALL 以 `(player_id, task_id)` 为复合主键，并保存可空 `time_1`、可空 `time_2`、非负 `exception`、严格 JSON 字符串 `meta`、`created_at` 和 `updated_at`。任务行 SHALL 通过外键关联玩家并在玩家删除时级联删除。

系统 SHALL NOT 在玩家任务行中复制 Handler dependencies、revision、Handler 代码或完整任务定义。

#### Scenario: 添加已注册任务

- **WHEN** 可写 Player 使用 `add_task(task_id)` 添加当前 TaskCatalog 中存在的任务
- **THEN** 系统 SHALL 创建一个初始时间为空、错误次数为零且 meta 为空对象的任务行

#### Scenario: 重复添加任务保持幂等

- **WHEN** 玩家重复添加已经存在的任务
- **THEN** 系统 SHALL 保留现有时间、错误次数和 meta，不得隐式重置任务状态

#### Scenario: 移除任务

- **WHEN** 可写 Player 使用 `remove_task(task_id)` 移除任务
- **THEN** 系统 SHALL 删除该玩家对应任务行；任务不存在时操作 SHALL 保持幂等

### Requirement: TaskContext stages task state changes

TaskExecutor SHALL 使用当前任务行构造 TaskContext，并向 Handler 提供玩家、任务身份、`time_1`、`time_2`、`exception`、解析后的 meta 和统一 UTC 当前时间。TaskContext SHALL 提供设置 `extra_time`、替换或更新 meta、以及声明本次延后完成的方法。

Handler SHALL 不直接设置 `time_1` 或 `exception`，也不需要返回 TaskResult。Handler 正常返回且未声明延后时，TaskExecutor SHALL 使用 Handler 成功完成时间自动更新 `time_1`。Handler 抛出可识别任务错误时，TaskExecutor SHALL 不推进 `time_1`。

#### Scenario: Handler 正常完成

- **WHEN** Handler 正常返回且未调用延后方法
- **THEN** TaskExecutor SHALL 更新当前任务的 `time_1`，并保存 Context 中的 `time_2` 和 meta

#### Scenario: Handler 延后完成

- **WHEN** Handler 判断当前条件尚未满足并调用延后方法后正常返回
- **THEN** TaskExecutor SHALL 保留旧的 `time_1`，并保存 Handler 设置的其他任务状态

#### Scenario: Handler 修改 meta

- **WHEN** Handler 使用 Context 更新可 JSON 序列化的 meta
- **THEN** 系统 SHALL 在 Handler 正常完成后将更新后的 meta 保存为严格 JSON 字符串

#### Scenario: Handler 通过 Player 管理任务

- **WHEN** Handler 调用 `Player.tasks.add_task()` 或 `remove_task()`
- **THEN** 任务增删 SHALL 属于当前 Task transaction；本轮开始后新增的任务 SHALL 不在当前调度遍历中递归执行

### Requirement: Lazy execution occurs at accepted player activity points

系统 SHALL 在玩家注册或 Construct 激活、登录、已认证写命令开始前和显式任务处理请求中触发玩家任务处理。纯读取端点 SHALL NOT 因读取而隐式写入任务状态。

#### Scenario: 写命令触发任务处理

- **WHEN** 已认证玩家提交一个需要 `execute_with_task()` 的写命令
- **THEN** 系统 SHALL 在业务 Operation transaction 前提交该玩家的 Task transaction

#### Scenario: 登录触发任务处理

- **WHEN** 玩家成功完成登录流程
- **THEN** 系统 SHALL 处理该玩家已经存在的任务；Construct 新增的任务默认可延迟到后续触发点

#### Scenario: 读取端点不触发任务写入

- **WHEN** 玩家访问普通读取端点
- **THEN** 系统 SHALL 只读取当前状态，不得隐式创建、更新或删除玩家任务行

### Requirement: TaskExecutor reuses Player on the normal path

TaskExecutor SHALL 在一个 Task transaction 开始时根据当前任务集合求出 Handler 依赖并集，加载一个可写 Player 并在正常成功路径复用该 Player。TaskExecutor SHALL 将 `TASKS` 作为隐式依赖加入加载位图。

保存点回滚后，TaskExecutor SHALL 丢弃可能包含失效 Python 缓存的 Player，重新加载 Player，并继续处理本轮任务键集合中的后续任务。若不能可靠重建 Player 或转移事务 Hook 状态，Task transaction SHALL 直接失败。

#### Scenario: 多个任务共享一次 Interface 加载

- **WHEN** 当前玩家有多个任务且其 Handler 依赖多个 Player Interface
- **THEN** TaskExecutor SHALL 先求依赖并集并复用一个 Player 完成正常任务遍历

#### Scenario: 保存点回滚后重新加载

- **WHEN** 一个 Handler 错误导致当前保存点回滚且调度器继续处理后续任务
- **THEN** TaskExecutor SHALL 在后续 Handler 前使用反映数据库事务状态的新 Player 聚合

### Requirement: Task and Operation transactions are separate

系统 SHALL 提供 `execute_with_task()`，在一次 Request-ID 幂等生命周期内先执行并提交 Task transaction，再执行并提交 Operation transaction。Operation transaction SHALL 重新加载 Player。Operation 失败 SHALL NOT 回滚已经提交的 Task transaction。

#### Scenario: Task 成功且 Operation 成功

- **WHEN** Task transaction 和 Operation transaction 均成功
- **THEN** 系统 SHALL 缓存并返回 Operation 的最终响应

#### Scenario: Operation 失败

- **WHEN** Task transaction 已提交但 Operation transaction 失败
- **THEN** 系统 SHALL 回滚 Operation 变更，保留 Task transaction 的状态，并释放 Request-ID 缓存占位

#### Scenario: Request-ID 重放

- **WHEN** 客户端使用已经完成的 Request-ID 重试同一个写命令
- **THEN** 系统 SHALL 在启动 Task transaction 前返回缓存响应，不得再次执行任务 Handler

### Requirement: Handler errors use nested rollback and increment exception

TaskExecutor SHALL 在 Task 外层事务内为每个 Handler 创建 `session.begin_nested()` 保存点。可识别的 `TaskHandlerError` SHALL 回滚当前 Handler 的 PlayerInterface 和任务状态修改，在 Task 外层事务中增加对应任务的 `exception`，记录该任务失败，重载 Player，并继续处理本轮剩余任务。

任务外层事务、保存点控制、数据库读写、JSON 编解码、pre-commit hook 或提交失败 SHALL 直接抛出原始异常，TaskExecutor 不得执行复杂的二次补偿，Operation transaction 不得启动。

#### Scenario: 单个 Handler 错误

- **WHEN** Handler 抛出可识别的 `TaskHandlerError`
- **THEN** 系统 SHALL 回滚该 Handler 的保存点修改、增加 `exception`、报告该任务失败、重载 Player，并不得更新 `time_1`

#### Scenario: Handler 错误后继续后续任务

- **WHEN** 当前任务集合中第一个 Handler 抛出 `TaskHandlerError`，且 Player 和事务 Hook 状态能够被重新加载
- **THEN** 系统 SHALL 保留第一个任务的失败计数，并继续执行后续任务

#### Scenario: Task 外层提交失败

- **WHEN** Task transaction 的 flush 或 commit 失败
- **THEN** 系统 SHALL 回滚 Task transaction、直接抛出异常并跳过 Operation transaction

### Requirement: Task transaction retains pre-commit hook support

TaskExecutor SHALL 支持现有 `CommandPreCommitHook`，允许 Handler 通过 PlayerInterface 产生 checkpoint、Artifact 或其他既有事务前置提交行为。成功 Handler 的 Hook 状态 SHALL 被刷新到 Task transaction；失败 Handler 的保存点 SHALL NOT 刷新失败状态。Hook 或其外部持久化步骤失败时，Task transaction SHALL 直接失败。

#### Scenario: Task Handler 触发 checkpoint Hook

- **WHEN** Handler 通过 ProgressInterface 产生待提交 checkpoint
- **THEN** TaskExecutor SHALL 在 Task transaction 内运行现有 checkpoint Hook，并在 Task transaction 成功时保存对应数据库 metadata

#### Scenario: Task Handler 触发 Artifact 生成

- **WHEN** Handler 通过 ArtifactInterface 生成或刷新 Artifact
- **THEN** TaskExecutor SHALL 保持现有 Artifact 对象写入和 SQL 提交顺序，且 Operation transaction 不得覆盖 Task transaction 的已提交结果

#### Scenario: Task Hook 失败

- **WHEN** Task transaction 中的 pre-commit Hook 抛出异常
- **THEN** 系统 SHALL 回滚 Task transaction、直接抛出异常并跳过 Operation transaction

#### Scenario: Handler 取消或进程取消

- **WHEN** Handler 抛出任务系统不能安全恢复的取消异常
- **THEN** 系统 SHALL 回滚当前事务并直接重新抛出该异常

### Requirement: Task snapshot tracks registered identities

系统 SHALL 保存只包含当前有效任务注册身份集合及集合指纹的 Task Snapshot。Snapshot SHALL NOT 保存玩家任务状态、Handler dependencies 或 revision。启动 reconciliation SHALL 以当前 TaskCatalog 为权威集合，删除数据库中不存在于当前集合的玩家任务行，并在清理事务成功后写入新 Snapshot。

#### Scenario: 移除已注册任务

- **WHEN** 当前 TaskCatalog 不再包含数据库任务行的 `task_id`
- **THEN** 启动 reconciliation SHALL 删除所有对应玩家任务行

#### Scenario: 新增任务身份

- **WHEN** 当前 TaskCatalog 新增一个任务身份
- **THEN** 系统 SHALL 使该身份可供 `add_task()` 使用；除非任务显式声明自动绑定策略，否则不得为所有历史玩家批量创建任务行

#### Scenario: 空 Catalog 保护

- **WHEN** 当前 TaskCatalog 为空且数据库中存在玩家任务行
- **THEN** 启动 reconciliation SHALL 阻止应用进入 ready，不得静默删除全部任务

#### Scenario: Snapshot 清理成功后持久化

- **WHEN** 任务清理事务成功完成
- **THEN** 系统 SHALL 原子写入新的 Task Snapshot；清理失败时不得覆盖旧 Snapshot

### Requirement: Task HTTP endpoints expose semantic operations

系统 SHALL 暴露固定的玩家任务读取和显式处理接口：`GET /api/v1/tasks` 与 `POST /api/v1/tasks/process`。处理接口 SHALL 要求 Bearer JWT 和 UUID `Request-ID`，并 SHALL 使用 `execute_with_task()` 或任务专用命令事务。处理报告 SHALL 为本轮每个任务返回 `success` 或 `failure` 状态。系统 SHALL NOT 暴露任意任务身份到 Handler Callback 的通用执行路由。

#### Scenario: 查询任务状态

- **WHEN** 已认证玩家请求 `GET /api/v1/tasks`
- **THEN** 系统 SHALL 返回该玩家已激活任务的时间、错误次数和 meta 可公开状态，不得执行任务

#### Scenario: 显式处理任务

- **WHEN** 已认证玩家使用新的 Request-ID 请求 `POST /api/v1/tasks/process`
- **THEN** 系统 SHALL 在 Task transaction 中处理该玩家任务，并为每个任务返回成功或失败状态

#### Scenario: 拒绝任意 Callback 路由

- **WHEN** 客户端尝试通过任务身份直接调用 Handler
- **THEN** 系统 SHALL 不提供该通用路由
