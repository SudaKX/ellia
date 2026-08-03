# VirtualAccount API

## 登录

```http
POST /api/v1/vac/login
Authorization: Bearer <access token>
Request-ID: <UUID>
```

```json
{"username":"operator","password":"module-defined-password"}
```

成功返回当前账号和状态版本：

```json
{"content":{"current_account":{"account_id":"example.operator","username":"operator","display_name":"Operator","permission":5,"metadata":{},"created_at":"2026-08-03T00:00:00+00:00","last_logged_in_at":"2026-08-03T00:00:00+00:00","login_count":1},"version":2},"followups":[]}
```

账号未发放、账号已退休、用户名错误和密码错误均返回 RFC 9457 `401` Problem Details，type 为 `.../virtual-account-invalid-credentials`；它不触发平台 Token refresh。完整错误格式见 [错误与缓存](errors-and-caching.md)。

## 登出

```http
POST /api/v1/vac/logout
Authorization: Bearer <access token>
Request-ID: <UUID>
```

成功后 `current_account` 为 `null`。账号发放和删除不提供通用 HTTP 路由，只能由模块命令通过 `Player.accounts` 执行。
