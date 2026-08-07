# 验证系统

## 数据、Interface 与 Registry

验证没有 SQL 表、ORM Model 或独立 Player Interface。`ValidationRegistry` 以唯一 stable ID 和小写 slug validation ID 注册 `ValidationAttempt(stable_id, validation_id, handler)`，冻结为 `ValidationCatalog`。handler 接收可写 `CommandContext` 与 JSON 映射，返回 `ValidationOutcome(accepted)`，可修改 `player.progress`、生成 Artifact 或添加 followup。

## Service 与端点

`ValidationService` 将 handler 的 accepted 布尔值映射为 `ResponseSpec`。唯一端点为：

```text
POST /api/v1/validations/{validation_id}/attempts
Authorization: Bearer <access token>
Request-ID: <UUID>
```

Router 先从 Catalog 查找 attempt，再交给命令执行器。未知 validation 是 `404`；Request-ID 冲突和进度转移失败为 `409`；handler 可用 `context.reject()` 指定错误状态。成功响应统一为 `{content: {accepted: boolean}, followups: []}`。

## Example 与约束

Example 注册 validation ID `example-answer`。其 handler 仅在当前账号为 Guest 时规范化并接受 `answer`；Guest 首次正确提交推进进度、发放 Administrator 并生成 `ADMIN_ACCESS.txt`；Guest 在已完成状态下重复提交直接接受，其他当前账号仍返回拒绝。它说明 validation 是模块语义命令入口，而非可由模块自行新增的 HTTP 回调。

Request-ID 缓存仅进程内、短 TTL；对象存储副作用不能随 SQL 回滚。前端协议见 [验证契约](../api/validations.md) 和 [命令契约](../api/commands.md)。

相关实现：`registry/validations/`、`services/validations/`、`core/commands/`。
