# 命令 API 协议

验证提交和 checkpoint restore 都是命令。请求必须包含：

```http
Authorization: Bearer <access token>
Request-ID: <UUID>
```

成功响应统一包装：

```json
{"content": {}, "followups": []}
```

`content` 由具体端点定义；`followups` 是 JSON 对象数组，当前 Example 不产生 followup。客户端必须为一次用户意图生成一个 UUID；网络错误重试必须复用相同 ID，新的用户意图必须生成新 ID。

| 情况 | 状态 | 客户端动作 |
| --- | --- | --- |
| 同玩家完成后的重试 | 原成功状态和完全相同响应 | 接受缓存响应 |
| 同 ID 仍在执行 | `409`，含 `Retry-After: 1` | 短暂等待后用原 ID 重试 |
| 其他玩家使用同 ID | `409` | 生成新操作，不重用该 ID |
| handler 拒绝或进度冲突 | `409` 或 handler 指定状态 | 刷新相关状态后提示失败 |

幂等缓存仅在当前进程 TTL 内有效，客户端不能将其视为永久去重机制。内部事务、checkpoint 和对象存储限制见 [命令事务](../architecture/command-transactions.md)。
