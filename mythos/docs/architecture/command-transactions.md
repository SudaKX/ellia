# 命令事务与幂等

## 职责与持久化

命令框架没有 SQL 表、ORM Model、Registry 或独立 HTTP Router。`CommandTransactionExecutor` 为 validation 和 checkpoint restore 提供同一写入边界；`RequestCache` 是进程内 TTLCache，不是持久化请求日志。

## 调用流

```text
Command Router -> JWT identity + AsyncSession
  -> RequestCache.reserve(Request-ID, player)
  -> session.begin()
  -> writable Player with progress + artifacts
  -> CommandContext -> Service / module handler
  -> pre-commit hooks -> commit -> cache completed response
```

`ResponseSpec` 定义状态码、JSON `body` 和响应头；成功命令统一返回 `{ "content": <body>, "followups": [...] }`。`FollowupCollector` 只接受可 JSON 序列化的对象。异常会回滚 SQL 事务并释放 Request-ID 占位。

## HTTP 契约

当前使用者是：

- `POST /api/v1/validations/{validation_id}/attempts`
- `POST /api/v1/progress/checkpoints/restore`

两者均要求 Bearer JWT 和 UUID `Request-ID` 请求头。相同玩家在 TTL 内重放已完成 ID 返回缓存响应；执行中或由其他玩家使用则返回 `409`。完整契约见 [命令 API](../api/commands.md)。

## Hook、Example 与限制

当前唯一 hook 是 `ProgressCheckpointHook`：它把已暂存 checkpoint 写入本地 JSON，并增加 `PlayerProgressCheckpoint` ORM 记录。Example 的 validation handler 在该事务内推进 `example.completed` 并生成 Artifact；对象上传先于 SQL 提交，因此回滚可能留下对象存储孤儿。

相关对象：`CommandContext`、`ResponseSpec`、`CachedResponse`、`RequestCache`、`PendingCheckpoint`。相关实现：`core/commands/`、`core/followups.py`、`services/progress/checkpoint_hook.py`。
