# 命令事务与幂等

## 职责与持久化

命令基础设施没有自己的 SQL 表或 ORM Model。`mythos.commands` 提供 `RequestCache`、`PipelinedTransaction`、`EndpointCommandExecutor` 和 `TaskCommandExecutor`；两个 Executor 分别负责 HTTP 普通写命令和任务处理端点。`RequestCache` 是进程内 TTLCache，不是持久化请求日志。

`TaskService`、各领域 Service、Auth Workflow 和 reconciliation 都是事务内参与者。Service 可以修改调用方提供的 writable `Player`，但不拥有外层 transaction，不提交或回滚 Session，也不管理 Request-ID 或 HTTP 响应。

## 调用流

```text
Endpoint -> JWT identity + AsyncSession
  -> RequestCache lease(Request-ID, player)
  -> Task transaction (普通写命令默认开启)
       -> TaskService.run_itx()
       -> TaskContext -> Task Handler -> nested savepoint / hooks
       -> commit
  -> Operation transaction
       -> PlayerLoader.lock/load writable Player
       -> CommandContext -> Domain Service / module handler
       -> optional post-operation phases
       -> ordered pre-commit hooks -> commit
  -> lease.complete(CachedResponse)
```

一个 Request-ID lease 可以覆盖多个物理 transaction。Task transaction 已提交而 Operation 失败时，Operation 回滚、Task 状态保留，lease 释放以便后续请求重试；已完成的 Request-ID 在 Task transaction 开始前直接返回原始响应。

`ResponseSpec` 定义状态码、JSON `body` 和响应头；Endpoint Executor 成功完成时统一包装 `{ "content": <body>, "followups": [...] }`。`FollowupCollector` 只接受可 JSON 序列化的对象。lease 上下文在异常或未完成响应时自动 release。

## HTTP 契约

普通写端点通过 `EndpointCommandExecutor.execute()` 执行，默认先处理惰性 Task，再执行重新加载 Player 的 Operation transaction。只有明确的补偿或 no-task 入口可以显式关闭 Task phase；普通业务 Endpoint 不传关闭选项。

当前普通命令使用者是：

- `POST /api/v1/validations/{validation_id}/attempts`
- `POST /api/v1/progress/checkpoints/restore`
- `POST /api/v1/hints/{hint_id}/disclose`
- `POST /api/v1/vac/login`
- `POST /api/v1/vac/logout`

`POST /api/v1/tasks/process` 使用 `TaskCommandExecutor`，在一个 Task transaction 内运行 `TaskService.run_itx()` 并返回 `TaskRunReport`；它不经过普通 Player Operation Pipeline，也不会重复执行 Task phase。以上端点均要求 Bearer JWT 和 UUID `Request-ID` 请求头。

## Hook、Example 与限制

当前唯一 hook 是 `ProgressCheckpointHook`：它把已暂存 checkpoint 写入本地 JSON，并增加 `PlayerProgressCheckpoint` ORM 记录。普通 Operation 和 Task Handler 都可以触发该 Hook；TaskService 在成功 Handler 的保存点内刷新 Hook。Example 的 validation handler 在 Operation transaction 内推进 `example.completed` 并生成 Artifact；对象上传先于 SQL 提交，因此回滚可能留下对象存储孤儿。

HTTP Router 位于 `mythos.endpoints`，由 `endpoints.router` 聚合后挂载。Service 和内部 Workflow 不依赖 FastAPI Router、RequestCache 或 Endpoint Executor。相关对象：`CommandContext`、`ResponseSpec`、`CachedResponse`、`RequestCache`、`PlayerLoader`、`PipelinedTransaction`、`PendingCheckpoint`。相关实现：`commands/`、`endpoints/`、`core/followups.py`、`services/progress/checkpoint_hook.py`。
