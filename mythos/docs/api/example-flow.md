# Example API 调用流

开发页面位于 `/example/`，但数据 API 都使用 `/api/v1`。它的交互顺序是：

```text
POST /auth/register 或 /auth/login
  -> 并行 GET /credits, /tasks, /hints, /progress, /files/d/version, /scripts
  -> `/files/d/version` 返回新的 `pft4_` 时 GET /files/d/tree；命中 304 时复用现有树
  -> 页面展示 VTB 余额、自动恢复任务状态与当前可见 Hint
  -> 顶部刷新只重复 GET；点击“立即处理”时 POST /tasks/process + Request-ID
  -> POST /hints/{hint_id}/disclose + Request-ID
  -> 成功后重新 GET /credits 与 /hints
  -> GET /hints/{hint_id}/{content_token}/content-url
  -> 直接 fetch 预签名 Hint 对象 URL 并在 Hint 预览中展示
  -> POST /vac/login (guest credentials) + Request-ID
  -> 强制刷新 credits、hints、progress、/files/d/version、/files/d/tree、scripts
  -> 用户提交 answer
  -> POST /validations/example-answer/attempts + Request-ID
  -> 强制刷新 credits、hints、progress、/files/d/version、/files/d/tree、scripts
  -> GET /files/{admin_access_file_id}/{content_token}/content-url；412 时刷新动态树并重试一次
  -> POST /vac/login (administrator credentials) + Request-ID
  -> 再次强制刷新 credits、hints、progress、/files/d/version、/files/d/tree、scripts
  -> GET /files/{file_id}/{content_token}/content-url
  -> 直接 fetch 预签名对象 URL
```

初始只有 `/public` 可见。Guest 登录后可提交 `echo-7`；成功后动态 `/archive` 包含玩家专属 `ADMIN_ACCESS.txt`，其 token 使用 `act3_`。Administrator 登录后 `/admin/CONTROL.txt` 可见。相同 Request-ID 用于网络重试，成功后新的用户提交使用新的 ID。

Example 的两个公开 Hint 在认证后可见，价格为 2 和 3 VTB；完成 Echo 后第三个价格为 5 VTB 的 Hint 出现。开发/测试新玩家注册后初始拥有 5 VTB；第一次认证写操作、logout 或显式任务处理会惰性触发 `example.vtb-allowance`，按当前余额最多补发 5 VTB。之后任务按已到期的 60 秒周期补发，每次任务发放后的余额不超过 10 VTB。测试界面通过 `GET /api/v1/tasks` 展示 `time_2`、倒计时和 meta；倒计时到期只标记任务可处理，不自动请求，主动控件使用 `POST /api/v1/tasks/process`。

Example 页面不会读取 `/files/tree` 或 `/files/version` 来展示文件，因为二者不包含 Artifact。完整系统行为见 [Example 模块](../modules/example.md)。
