# 命令事务与幂等

## 职责与持久化

命令基础设施没有自己的 SQL 表或 ORM Model。`mythos.commands` 提供 `RequestCache`、`PipelinedTransaction`、`EndpointCommandExecutor`、`AchievementCommandExecutor` 和 `TaskCommandExecutor`；三个 Executor 分别负责普通写命令、成就 check/claim 和任务处理端点。`RequestCache` 是进程内 TTLCache，不是持久化请求日志。

`TaskService`、各领域 Service、Auth Workflow 和 reconciliation 都是事务内参与者。Service 可以修改调用方提供的 writable `Player`，但不拥有外层 transaction，不提交或回滚 Session，也不管理 Request-ID 或 HTTP 响应。

## 调用流

```text
Endpoint -> JWT identity + AsyncSession
  -> RequestCache lease(Request-ID, player)
  -> Task transaction (普通写命令默认开启)
       -> ContextScope.http()
        -> PlayerLoader lock/load writable Player once
        -> one Task batch savepoint
        -> PipelinedTransaction -> TaskService.run_loaded(...)
        -> TaskContext -> all Task Handlers
        -> one ordered pre-commit hook phase
        -> commit
  -> Operation transaction
       -> PlayerLoader.lock/load writable Player
        -> CommandContext(scope) -> Domain Service / module handler
        -> ordered pre-commit hooks -> commit
   -> Achievement Check transaction
        -> condition + earned records -> commit
   -> Achievement Effect transaction
        -> immediate effects + claimed_at
        -> ordered pre-commit hooks -> commit
   -> append safe warn -> lease.complete(CachedResponse)
```

一个 Request-ID lease 可以覆盖多个物理 transaction。Task transaction 已提交而 Operation 失败时，Operation 回滚、Task 状态保留，lease 释放以便后续请求重试；已完成的 Request-ID 在 Task transaction 开始前直接返回原始响应。

`ResponseSpec` 定义状态码、JSON `body` 和响应头；Endpoint/Response adapter 在成功完成时统一包装 `{ "content": <body>, "followups": [...] }`。Core `FollowupCollector` 只收集可变 `Followup(action, data)` 并维护 checkpoint rollback，不导入 FastAPI；响应边界调用 `Followup.to_json()`，再由 `ResponseSpec` 执行 JSON object 校验，silent sink 丢弃 best-effort Followup。lease 上下文在异常或未完成响应时自动 release。

## HTTP 契约

普通写端点通过 `EndpointCommandExecutor.execute()` 执行，默认先处理惰性 Task，再执行重新加载 Player 的 Operation transaction。Operation 提交后，Executor 在独立 transaction 中运行成就 Check 和需要的 Effect；C/D 失败不影响 Operation，只在最终缓存响应中增加安全 `warn`。只有明确的补偿或 no-task 入口可以显式关闭 Task phase；普通业务 Endpoint 不传关闭选项。

当前普通命令使用者是：

- `POST /api/v1/validations/{validation_id}/attempts`
- `POST /api/v1/progress/checkpoints/restore`
- `POST /api/v1/hints/{hint_id}/disclose`
- `POST /api/v1/vac/login`
- `POST /api/v1/vac/logout`
- `POST /api/v1/achievement/check` 和 `POST /api/v1/achievement/claim/{public_id}` 使用独立的 `AchievementCommandExecutor`，不执行 Task 或普通 Operation。

`POST /api/v1/tasks/process` 使用 `TaskCommandExecutor`，由前端决定调用时机，在一个 Task transaction 内锁定并加载 Player、创建一个 Task batch savepoint、运行 `PipelinedTransaction` 和 `TaskService.run_loaded()`，成功后返回 `TaskRunReport`；它不经过普通 Player Operation Pipeline，也不会重复执行 Task 或 Achievement phase。Auth 的 register、login、logout 和 refresh 由 Auth Workflow 直接执行，不包含 Task 或 Achievement phase；logout 不调用 `/tasks/process`。以上需要 Request-ID 的 HTTP 命令均要求 Bearer JWT 和 UUID `Request-ID` 请求头。

## Hook、Example 与限制

当前唯一 hook 是 `ProgressCheckpointHook`：它把已暂存 checkpoint 写入本地 JSON，并增加 `PlayerProgressCheckpoint` ORM 记录。普通 Operation、Task Handler 和 Achievement Effect 都可以触发该 Hook；Task CommandExecutor 在所有 Task Handler 成功后统一刷新 Hook。Achievement Effect 使用单个 batch transaction，不为每个 effect 创建 savepoint。Example 的 validation handler 在 Operation transaction 内推进 `example.completed` 并生成 Artifact；对象上传先于 SQL 提交，因此回滚可能留下对象存储孤儿。

HTTP Router 位于 `mythos.endpoints`，由 `endpoints.router` 聚合后挂载。Service 和内部 Workflow 不依赖 FastAPI Router、RequestCache 或 Endpoint Executor；共享 `PipelinedTransaction` 不保存 request-specific scope。相关对象：`ContextScope`、`CommandContext`、`TaskContext`、`ResponseSpec`、`CachedResponse`、`RequestCache`、`PlayerLoader`、`PipelinedTransaction`、`PendingCheckpoint`。相关实现：`commands/`、`endpoints/`、`core/followups.py`、`services/progress/checkpoint_hook.py`。
