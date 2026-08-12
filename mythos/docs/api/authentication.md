# 认证 API

## 端点

| 方法 | 路径 | 请求 | 成功 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/register` | `CredentialsRequest` | `201` + token JSON + refresh cookie |
| POST | `/api/v1/auth/login` | `CredentialsRequest` | `200` + token JSON + refresh cookie |
| POST | `/api/v1/auth/refresh` | refresh cookie | `200` + 新 token/cookie |
| POST | `/api/v1/auth/logout` | Bearer token | `204` + 删除 refresh cookie |

`CredentialsRequest`：`{"username":"example-player","password":"correct-horse-battery"}`。username 经过 trim/NFKC 校验，长度为 3--32 且不能有空白或控制字符；password 长度为 8--128。

成功 token DTO：

```json
{"access_token":"<JWT>","token_type":"bearer","expires_in":900}
```

## 客户端规则

- register/login 后将 access token 保存在内存，后续 API 添加 Bearer header；不要持久化 refresh cookie 或预签名 URL。
- 浏览器携带 cookie 调用 `/refresh`；refresh 无效返回 RFC 9457 `401` Problem Details，type 为 `.../refresh-credential-invalid`，并清除 cookie，客户端应清空会话。
- logout 需要 Bearer token，返回 `204`；客户端无论网络失败与否都应清空本地 token。
- 所有认证响应设置 `Cache-Control: no-store`。refresh cookie 是 HttpOnly、SameSite Strict，路径限定为 `/api/v1/auth`。

错误：register 的重复用户名为 `409`，type 为 `.../username-already-exists`；login 错误用户名或密码为 `401`，type 为 `.../primary-credentials-invalid`。Bearer 缺失和无效分别为 `.../access-token-missing`、`.../access-token-invalid`。Problem Details 格式见 [错误与缓存](errors-and-caching.md)。
