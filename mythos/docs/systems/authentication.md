# 认证系统

## 职责与持久化

认证管理用户名、密码哈希、JWT access token 与轮换 refresh cookie。它拥有 `players` / `PlayerRecord` 和 `player_auth` / `PlayerAuth` 两张表：前者保存 UUID、展示用户名、规范化唯一用户名和访问时间；后者以玩家 UUID 为主键保存 Argon2 哈希和 refresh selector、HMAC 摘要、过期与轮换时间。

认证没有 `PlayerInterface`、内容 Registry 或冻结 Catalog。它产生最小的 `PlayerIdentity(player_id)`，其他系统再用该 ID 创建请求级 Player。

## Service、端点与数据对象

`AuthService` 是每个认证请求创建的对象，直接持有当前 `AsyncSession`、`Settings` 和冻结的 `ProgressGraph`。路由位于 `/api/v1/auth`：

| 方法 | 路径 | 成功结果 |
| --- | --- | --- |
| POST | `/register` | `201`、`AccessTokenResponse`、refresh cookie |
| POST | `/login` | `200`、`AccessTokenResponse`、轮换 refresh cookie |
| POST | `/refresh` | `200`、新的 token/cookie；无效时 `401` 并删除 cookie |
| POST | `/logout` | `204`、清除数据库 refresh 凭据和 cookie |

请求对象 `CredentialsRequest` 限制 username 为 3--32 字符、password 为 8--128 字符；响应对象为 `{access_token, token_type: "bearer", expires_in}`。`RefreshCredential` 的 selector 与 secret 只在 cookie 中合并传递，数据库不保存明文 secret。

## 注册副作用与 Example

注册在一个事务中创建 `PlayerRecord`、`PlayerAuth`、`PlayerProgress`、`PlayerVirtualAccountState` 和 `PlayerCredits`，并用 `ProgressGraph.entry_node_ids` 初始化 unlocked/frontier。随后 `PlayerConstructedEvent` listener 发放模块账号和其他初始状态。Example 因此在注册后立即显示 `example.entry`；它不注册认证内容。

## 重要约束

- access token 使用 HS256，验证 issuer、audience、时间字段和 `typ="access"`。
- refresh cookie 固定为 HttpOnly、SameSite Strict、路径 `/api/v1/auth`，所有认证响应使用 `Cache-Control: no-store`。
- refresh 使用带旧 selector 和旧摘要条件的更新，避免并发复用同一 refresh credential。
- API 消费规则见 [认证契约](../api/authentication.md)。

相关实现：`auth/`、`persistence/models/player.py`、`persistence/models/auth.py`。
