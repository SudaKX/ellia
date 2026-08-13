# 验证 API

```http
POST /api/v1/validations/{validation_id}/attempts
Authorization: Bearer <access token>
Request-ID: <UUID>
Content-Type: application/json
```

payload 是模块定义的 JSON 对象。Example 请求为：

```json
{"answer":" ECHO-7 "}
```

成功响应：

```json
{"content":{"accepted":true},"followups":[]}
```

`accepted: false` 是正常业务拒绝，仍返回 `200`；前端应保留当前页面状态。Validation Handler 可通过 `context.reject(reason, details)` 表达领域冲突，但不能指定 HTTP status；Endpoint 固定返回 `409 validation-rejected` Problem Details。未知 `validation_id` 为 `404`，进度前置条件不满足或 Request-ID 冲突为 `409`，JWT 无效为 `401`。正确答案后必须重新请求 progress、scripts 与动态文件树，因为服务端可能同时推进进度、产生 checkpoint 或生成 Artifact。

重试规则见 [命令 API](commands.md)，模块 handler 约束见 [验证系统](../systems/validations.md)。
