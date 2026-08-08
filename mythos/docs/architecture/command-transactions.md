# 命令事务与幂等

## 职责与持久化

命令框架没有自己的 SQL 表或 ORM Model。`CommandTransactionExecutor` 为 validation、checkpoint restore、Hint disclosure、VirtualAccount 登录/登出和惰性任务处理提供写入边界；`RequestCache` 是进程内 TTLCache，不是持久化请求日志。

## 调用流

```text
Command Router -> JWT identity + AsyncSession
  -> RequestCache.reserve(Request-ID, player)
  -> Task transaction (optional)
       -> writable Player with the union of Task Handler dependencies
       -> TaskContext -> Task Handler -> nested savepoint / hooks
       -> commit
  -> Operation transaction
       -> writable Player with operation interfaces
       -> CommandContext -> Service / module handler
       -> pre-commit hooks -> commit
  -> cache completed response
```

`ResponseSpec` 定义状态码、JSON `body` 和响应头；成功命令统一返回 `{ "content": <body>, "followups": [...] }`。`FollowupCollector` 只接受可 JSON 序列化的对象。异常会回滚 SQL 事务并释放 Request-ID 占位。

## HTTP 契约

当前使用者是：

- `POST /api/v1/validations/{validation_id}/attempts`
- `POST /api/v1/progress/checkpoints/restore`
- `POST /api/v1/hints/{hint_id}/disclose`
- `POST /api/v1/vac/login`
- `POST /api/v1/vac/logout`
- `POST /api/v1/tasks/process`

以上端点均要求 Bearer JWT 和 UUID `Request-ID` 请求头。带任务的写命令使用 `execute_with_task()`，在一次 Request-ID 生命周期内先提交 Task transaction，再提交 Operation transaction。相同玩家在 TTL 内重放已完成 ID 会在任务阶段开始前返回缓存响应；执行中或由其他玩家使用则返回 `409`。完整契约见 [命令 API](../api/commands.md) 和 [任务 API](../api/tasks.md)。

## Hook、Example 与限制

当前唯一 hook 是 `ProgressCheckpointHook`：它把已暂存 checkpoint 写入本地 JSON，并增加 `PlayerProgressCheckpoint` ORM 记录。普通 Operation 和 Task Handler 都可以触发该 Hook；TaskExecutor 在成功 Handler 的保存点内刷新 Hook。Example 的 validation handler 在 Operation 事务内推进 `example.completed` 并生成 Artifact；对象上传先于 SQL 提交，因此回滚可能留下对象存储孤儿。

相关对象：`CommandContext`、`ResponseSpec`、`CachedResponse`、`RequestCache`、`PendingCheckpoint`。相关实现：`core/commands/`、`core/followups.py`、`services/progress/checkpoint_hook.py`。
