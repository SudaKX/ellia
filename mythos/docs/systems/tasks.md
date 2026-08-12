# 惰性任务系统

## Registry 与 Handler

模块通过独立的 `TaskRegistry` 注册异步 Handler。Handler 使用稳定的 `task_id`，接收一个 `TaskContext`，并在注册时声明需要加载的 `PlayerInterfaces`。任务依赖只存在于冻结后的 `TaskCatalog` 运行时索引，不复制到玩家任务表。

TaskRegistry freeze 后拒绝新注册。当前实现没有任务 revision；同一 `task_id` 始终调用当前冻结的 Handler，因此 Handler 必须保持既有 `time_1`、`time_2` 和 `meta` 语义兼容。Task Snapshot 只保存注册身份集合和集合指纹。

## 持久化与 Interface

`player_task_states` 保存 `(player_id, task_id)`、`time_1`、`time_2`、`exception`、JSON 字符串 `meta` 和审计时间。任务行存在即表示任务已激活；`Player.tasks.add_task()` 和 `remove_task()` 是可写 Player 上的幂等操作。玩家删除时任务行级联删除。

`TaskContext` 是统一 `Context` 的可变子类，向 Handler 提供任务状态、玩家、任务身份、统一 UTC 当前时间和 per-call `ContextScope`。Handler 可以调用 `set_extra_time()`、更新 meta、`defer()` 或 `follow(Followup)`；正常返回且未 defer 时，`TaskService` 自动更新 `time_1`。错误次数由 Service 维护，Handler 不直接修改 `exception`。

## 惰性触发与事务

任务只在以下时机处理：

- 非 Auth 的已认证写操作开始前；
- 已认证写命令的 `EndpointCommandExecutor.execute()` 默认 Task 前置阶段；
- 前端显式请求 `POST /api/v1/tasks/process`。

Construct 生命周期可以激活任务，但 Auth Workflow 不执行 Task Handler。普通 GET 不隐式写入任务。CommandExecutor 为一次逻辑请求创建 collecting scope，在 Task transaction 中锁定并加载一次带 `TASKS` 的可写 Player，求当前 Handler 依赖并集，并通过 `PipelinedTransaction` 执行完整 Task 批次。整个批次使用一个 `session.begin_nested()` 保存点；成功后统一运行一次 pre-commit hooks，普通 Handler 异常失败时回滚批次、增加对应任务的 `exception`，提交计数后停止命令，不重载 Player，也不继续后续任务；取消和其他 `BaseException` 不计数并直接失败。Auth、reconciliation 等非 HTTP Workflow 不自动处理任务。

Task transaction 保留现有 pre-commit hook。多个 Handler 的 checkpoint、Artifact 或其他 PlayerInterface 变更在批次成功后统一触发 Hook；Hook 失败、数据库错误、JSON 错误、保存点控制错误和提交错误直接回滚并终止任务阶段。失败批次不保存 checkpoint。

普通写命令的 `EndpointCommandExecutor.execute()` 只保留一次 Request-ID lease，但依次提交 Task transaction 和 Operation transaction。Operation transaction 重新加载 Player；Operation 失败不会回滚已提交的任务状态。成功的任务报告包含每个任务的 `success` 状态；可识别 Handler 失败不返回部分报告。`POST /api/v1/tasks/process` 使用独立的 `TaskCommandExecutor`，由前端决定调用时机，只运行一次 Task phase。Auth 的 register、login、logout 和 refresh 不执行 Task；logout 不调用 `/tasks/process`。

注册、登录、登出和 refresh 由 `AuthService` 在各自的认证事务中直接处理认证和生命周期逻辑，不调用 TaskService；Construct 激活的任务由前端后续决定是否请求 `/api/v1/tasks/process`。这些认证流程不使用命令 Request-ID 包装。

## Snapshot 清理

启动期 Task reconciliation 以当前 TaskCatalog 为权威集合，删除数据库中不再注册的任务身份，然后原子写入新的 Task Snapshot。Snapshot 缺失时仍执行未知任务清理；当前 Catalog 为空但数据库存在任务时阻止应用 ready，避免误删全部任务。

新增任务身份默认只使 `add_task()` 可用，不会自动为所有历史玩家创建任务行。

## Example VTB allowance

Example 在 Construct 的晚优先级 Handler 中通过 `Player.tasks.add_task()` 激活 `example.vtb-allowance`。重复 Construct 或重复激活不会重置已有任务状态。该任务声明 `PlayerInterfaces.CREDITS` 依赖，不创建后台调度器，只在现有任务触发点运行。

任务首次有效处理时读取当前 `player.credits.vtb`，发放 `min(5, 10 - current_vtb)`，并把下一次到期时间写入 `time_2`。首次奖励完成后，Handler 在当前时间早于 `time_2` 时调用 `defer()`，保持 `time_1`、VTB 和 `meta` 不变；到期时按已过去的 60 秒周期每周期发放 1 VTB，一次请求可以补算多个周期。任务发放后的余额不超过 10；达到上限时任务安排下一次检查，不累积无限欠账。

Example `meta` 是严格 JSON 对象，当前 schema 形状如下：

```json
{
  "schema_version": 1,
  "initial_grant_applied": true,
  "total_granted": 5,
  "last_granted_at": "2026-08-09T12:00:00+00:00"
}
```

`total_granted` 是任务累计发放量，`last_granted_at` 是最近一次实际发放时间。VTB 上限判断始终读取当前 Credits Interface，不信任 `meta` 中的累计值。`GET /api/v1/tasks` 只读任务状态；`POST /api/v1/tasks/process` 才会显式处理当前玩家任务。

相关实现：`registry/tasks/`、`players/interfaces/tasks.py`、`commands/`、`endpoints/tasks.py`、`services/tasks/`、`persistence/models/tasks.py`。
