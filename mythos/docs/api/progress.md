# 进度 API

## 读取

```http
GET /api/v1/progress
Authorization: Bearer <access token>
```

```json
{
  "current_account":"PLAYER",
  "unlocked_nodes":["example.entry"],
  "frontier_nodes":["example.entry"],
  "checkpoint_sequence":-1,
  "version":1
}
```

节点 ID 是模块字符串 ID，不是数据库数字 ID。`version` 在成功的 `push()` 或 restore 后递增；前端在它改变后应重新获取受进度保护的文件和脚本。

## 恢复

```http
POST /api/v1/progress/checkpoints/restore
Authorization: Bearer <access token>
Request-ID: <UUID>
```

成功为：

```json
{"content":{"progress":{"current_account":"PLAYER","unlocked_nodes":[],"frontier_nodes":[],"checkpoint_sequence":0,"version":2}},"followups":[]}
```

没有 checkpoint 返回 `404`；文件、玩家、图结构或节点状态不兼容返回 `409`。请求 ID 规则见 [命令 API](commands.md)，领域规则见 [进度系统](../systems/progress-and-checkpoints.md)。
