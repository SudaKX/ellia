# Example API 调用流

开发页面位于 `/example/`，但数据 API 都使用 `/api/v1`。它的交互顺序是：

```text
POST /auth/register 或 /auth/login
  -> GET /files/tree?path=/public
  -> POST /vac/login (guest credentials) + Request-ID
  -> 并行 GET /progress, /files/d/version, /files/d/tree, /scripts
  -> 用户提交 answer
  -> POST /validations/example-answer/attempts + Request-ID
  -> GET /files/{admin_access_file_id}/{content_token}/content-url
  -> POST /vac/login (administrator credentials) + Request-ID
  -> 再次并行刷新 progress、静态/动态 tree、scripts
  -> GET /files/{file_id}/{content_token}/content-url
  -> 直接 fetch 预签名对象 URL
```

初始只有 `/public` 可见。Guest 登录后可提交 `echo-7`；成功后动态 `/archive` 包含玩家专属 `ADMIN_ACCESS.txt`，其 token 使用 `act3_`。Administrator 登录后 `/admin/CONTROL.txt` 可见。相同 Request-ID 用于网络重试，成功后新的用户提交使用新的 ID。

Example 页面不会读取 `/files/tree` 或 `/files/version` 来展示文件，因为二者不包含 Artifact。完整系统行为见 [Example 模块](../modules/example.md)。
