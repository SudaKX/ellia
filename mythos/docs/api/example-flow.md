# Example API 调用流

开发页面位于 `/example/`，但数据 API 都使用 `/api/v1`。它的交互顺序是：

```text
POST /auth/register 或 /auth/login
  -> 并行 GET /progress, /files/d/version, /files/d/tree, /scripts
  -> 用户提交 answer
  -> POST /validations/example-answer/attempts + Request-ID
  -> 再次并行刷新 progress、动态 version/tree、scripts
  -> GET /files/{file_id}/{content_token}/content-url
  -> 直接 fetch 预签名对象 URL
```

初始动态树只有 `/public`；正确提交 `echo-7` 后，动态 `/archive` 包含静态 `result.txt` 和玩家专属 `recovery-report.txt`。报告 token 使用 `act2_`。相同 Request-ID 用于网络重试，成功后新的用户提交使用新的 ID。

Example 页面不会读取 `/files/tree` 或 `/files/version` 来展示文件，因为二者不包含 Artifact。完整系统行为见 [Example 模块](../modules/example.md)。
