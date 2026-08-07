# Credits 与 Hint API

所有 Credits 与 Hint API 均要求 Bearer Token。Hint 内容本身从 RustFS/S3 预签名 URL 读取，不经 Mythos 代理传输。

| 方法 | 路径 | Request-ID | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/credits` | 否 | 返回当前玩家的 VTB 余额与余额版本 |
| GET | `/api/v1/hints` | 否 | 返回当前可见 Hint 元数据和已购买状态 |
| POST | `/api/v1/hints/{hint_id}/disclose` | 是 | 购买或幂等返回已拥有 Hint |
| GET | `/api/v1/hints/{hint_id}/{content_token}/content-url` | 否 | 为已购买 Hint 签发 inline RustFS/S3 URL |

Credits 响应示例：

```json
{
  "vtb": 5,
  "version": 1
}
```

Credits 响应使用 `Cache-Control: no-store` 和 `Vary: Authorization`。Hint 列表不返回当前 VTB 余额；每项包含公开 `hint_id`、`display`、当前 `vtb_cost`、媒体类型、尺寸与 `disclosed`；仅已购买项包含 `content_token`。

```json
{
  "hints": [{
    "hint_id": "h1_...",
    "display": {"title": "Echo 的第一条线索", "teaser": "检查重复片段", "icon": "hint", "sort_order": 1},
    "vtb_cost": 3,
    "media_type": "text/plain; charset=utf-8",
    "size_bytes": 42,
    "disclosed": true,
    "content_token": "hv1_..."
  }]
}
```

购买成功的命令响应为 `{ "content": { "hint": <Hint metadata> }, "followups": [] }`。余额不足返回 `409 insufficient-credits`；不存在的 Hint 返回 `404 hint-not-found`；disclose 时不可用 Hint 返回 `409 hint-unavailable`。

content URL 响应为 `{url, expires_at, content_token}`，token 为当前 Hint 的 `hv1_` version，带 token ETag、`Vary: Authorization` 与私有缓存策略。未购买或当前不可用时返回 `403 hint-unavailable`；旧 version 返回 `412 hint-content-version-mismatch`；客户端刷新 Hint 列表后最多重试一次。预签名 URL 不应写入持久化前端状态。

## Example 演示

development/test 环境中新 Construct 的 example 玩家获得一次性 5 VTB；production 不自动发放。Example 页面先并行读取 Credits 与 Hint 列表，购买后刷新二者，再通过 content URL 揭示正文。余额不足时页面会实际请求购买接口并展示 `insufficient-credits`，而不是只在前端禁用按钮。
