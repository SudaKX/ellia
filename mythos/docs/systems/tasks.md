# 惰性任务系统

## Registry 与 Handler

模块通过独立的 `TaskRegistry` 注册异步 Handler。Handler 使用稳定的 `task_id`，接收一个 `TaskContext`，并在注册时声明需要加载的 `PlayerInterfaces`。任务依赖只存在于冻结后的 `TaskCatalog` 运行时索引，不复制到玩家任务表。

TaskRegistry freeze 后拒绝新注册。当前实现没有任务 revision；同一 `task_id` 始终调用当前冻结的 Handler，因此 Handler 必须保持既有 `time_1`、`time_2` 和 `meta` 语义兼容。Task Snapshot 只保存注册身份集合和集合指纹。

## 持久化与 Interface

`player_task_states` 保存 `(player_id, task_id)`、`time_1`、`time_2`、`exception`、JSON 字符串 `meta` 和审计时间。任务行存在即表示任务已激活；`Player.tasks.add_task()` 和 `remove_task()` 是可写 Player 上的幂等操作。玩家删除时任务行级联删除。

`TaskContext` 向 Handler 提供任务状态、玩家、任务身份和统一 UTC 当前时间。Handler 可以调用 `set_extra_time()`、更新 meta 或 `defer()`；正常返回且未 defer 时，TaskExecutor 自动更新 `time_1`。错误次数由执行器维护，Handler 不直接修改 `exception`。

## 惰性触发与事务

任务只在以下时机触发：

- Construct 或业务 Handler 显式添加任务后；
- 登录完成后；
- 登出等已认证写操作开始前；
- 已认证写命令的 `execute_with_task()` 前置阶段；
- `POST /api/v1/tasks/process`。

普通 GET 不隐式写入任务。TaskExecutor 在 Task transaction 开始时读取当前任务键集合，求当前 Handler 依赖并集，加载并复用一个可写 Player。每个 Handler 使用 `session.begin_nested()` 保存点；`TaskHandlerError` 回滚当前 Handler、增加 `exception`、记录失败并重载 Player 后继续后续任务。

Task transaction 保留现有 pre-commit hook。成功 Handler 的 checkpoint、Artifact 或其他 PlayerInterface 变更可以触发 Hook；Hook 失败、数据库错误、JSON 错误、保存点控制错误和提交错误直接回滚并终止任务阶段。

`execute_with_task()` 只保留一次 Request-ID 生命周期，但依次提交 Task transaction 和 Operation transaction。Operation transaction 重新加载 Player；Operation 失败不会回滚已提交的任务状态。成功的任务报告包含每个任务的 `success` 或 `failure` 状态。

注册、登录和登出由 `AuthService` 在各自的认证事务中直接调用无缓存 TaskExecutor。这样任务基础设施失败时，注册玩家、refresh credential 和 logout 状态会与认证事务一起回滚；这些认证流程不使用命令 Request-ID 包装。

## Snapshot 清理

启动期 Task reconciliation 以当前 TaskCatalog 为权威集合，删除数据库中不再注册的任务身份，然后原子写入新的 Task Snapshot。Snapshot 缺失时仍执行未知任务清理；当前 Catalog 为空但数据库存在任务时阻止应用 ready，避免误删全部任务。

新增任务身份默认只使 `add_task()` 可用，不会自动为所有历史玩家创建任务行。

相关实现：`registry/tasks/`、`players/interfaces/tasks.py`、`services/tasks/`、`persistence/models/tasks.py`。
