# 脚本 API

```http
GET /api/v1/scripts
Authorization: Bearer <access token>
```

响应为：

```json
{"items":[{"stable_id":"example.boot","revision":"1","body":{"schema_version":1,"kind":"answer-validator"}}]}
```

只返回当前玩家通过 access rule 的脚本。`body` 是模块定义的 JSON 映射；客户端按 `kind` 和 `schema_version` 分派，不应假设未知 kind 的字段。Example 当前使用 `answer-validator`（含 validation ID、input、lines）和 `notice`（含 lines）。

端点无写入、Request-ID、缓存协商或专属错误映射；JWT 无效为 `401`。实现约束见 [脚本系统](../systems/scripts.md)。
