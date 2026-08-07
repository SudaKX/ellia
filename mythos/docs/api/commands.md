# 命令 API 协议

下列写入操作使用命令事务和 Request-ID：validation 提交、checkpoint restore、Hint disclosure、VirtualAccount 登录和登出。请求必须包含：

```http
Authorization: Bearer <access token>
Request-ID: <UUID>
```

成功响应统一包装：

```json
{"content": {}, "followups": []}
```

`content` 由具体端点定义；`followups` 是 JSON 对象数组，当前 Example 不产生 followup。`4xx` 和 `5xx` 不使用此包装，而是返回 RFC 9457 Problem Details。客户端必须为一次用户意图生成一个 UUID；网络错误重试必须复用相同 ID，新的用户意图必须生成新 ID。

| 方法 | 路径 | 领域操作 |
| --- | --- | --- |
| POST | `/api/v1/validations/{validation_id}/attempts` | 提交 validation |
| POST | `/api/v1/progress/checkpoints/restore` | 恢复 checkpoint |
| POST | `/api/v1/hints/{hint_id}/disclose` | 购买或幂等读取 Hint disclosure |
| POST | `/api/v1/vac/login` | 登录 VirtualAccount |
| POST | `/api/v1/vac/logout` | 登出 VirtualAccount |

| 情况 | 状态 | 客户端动作 |
| --- | --- | --- |
| 同玩家完成后的重试 | 原成功状态和完全相同响应 | 接受缓存响应 |
| 同 ID 仍在执行 | `409`；当前 validation、Hint 和 VirtualAccount 路由含 `Retry-After: 1`，checkpoint restore 暂未携带 | 短暂等待后用原 ID 重试 |
| 其他玩家使用同 ID | `409` | 生成新操作，不重用该 ID |
| handler 拒绝或进度冲突 | `409` 或 handler 指定状态 | 刷新相关状态后提示失败 |

幂等缓存仅在当前进程 TTL 内有效，客户端不能将其视为永久去重机制。内部事务、checkpoint 和对象存储限制见 [命令事务](../architecture/command-transactions.md)。
