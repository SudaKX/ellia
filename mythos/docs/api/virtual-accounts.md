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
{"content":{"current_account":{"account_id":"example.guest","username":"guest","display_name":"Guest Console","permission":10,"metadata":{"tier":"guest"},"created_at":"<ISO-8601>","last_logged_in_at":"<ISO-8601>","login_count":1},"version":2},"followups":[]}
```

账号未发放、账号已退休、用户名错误和密码错误均返回 RFC 9457 `401` Problem Details，type 为 `.../virtual-account-invalid-credentials`；它不触发平台 Token refresh。完整错误格式见 [错误与缓存](errors-and-caching.md)。

## 登出

```http
POST /api/v1/vac/logout
Authorization: Bearer <access token>
Request-ID: <UUID>
```

成功后 `current_account` 为 `null`。账号发放和删除不提供通用 HTTP 路由，只能由模块 EventBus listener 或命令通过 `Player.accounts` 执行。
