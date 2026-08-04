# API 错误与缓存

所有 `4xx` 和 `5xx` 响应使用 RFC 9457 `application/problem+json`，不使用命令成功响应的 `{content, followups}` 包装：

```json
{
  "type": "https://api.example.com/problems/access-token-invalid",
  "title": "Invalid access token",
  "status": 401,
  "detail": "The access token is invalid or expired.",
  "instance": "urn:uuid:..."
}
```

`MYTHOS_PROBLEM_TYPE_BASE_URL` 配置 Problem Type URI 基址，例如 `https://api.example.com/problems`；生产环境必须显式配置 HTTPS 基址，并由该站点提供各 Type 的人类可读说明。基址不能带用户信息、空白、查询或 fragment。客户端只使用稳定的 `type` URI 做逻辑判断，不解析 `detail`。`instance` 是服务端生成的单次错误关联 ID。字段校验会在顶层 `errors` 扩展中提供 JSON Pointer 和原因。

Bearer 认证失败不会主动发送 `WWW-Authenticate`。框架也不会移除 Router 或上游组件显式提供的该 Header。所有 Problem Details 响应使用 `Cache-Control: no-store`。只有 `type` 为 `.../access-token-invalid` 时才尝试一次 `/auth/refresh`；缺少 Token、主账号凭据错误、refresh 凭据错误和虚拟账号凭据错误都不触发刷新。

## Problem Types

下列 URI 均以 `MYTHOS_PROBLEM_TYPE_BASE_URL` 为前缀。`type` 是机器可读标识；title 和状态码固定，detail 仅描述本次请求。

| URI 后缀 | Title | 状态 | 含义 |
| --- | --- | --- | --- |
| `access-token-missing` | Access token required | `401` | 请求未提供平台 Access Token |
| `access-token-invalid` | Invalid access token | `401` | 平台 Access Token 无效或过期 |
| `primary-credentials-invalid` | Invalid username or password | `401` | 主账号用户名或密码错误 |
| `refresh-credential-invalid` | Invalid refresh credential | `401` | refresh cookie 无效、过期或已轮换 |
| `username-already-exists` | Username already exists | `409` | 注册用户名已被占用 |
| `virtual-account-invalid-credentials` | Invalid virtual account credentials | `401` | VirtualAccount 未发放、已退休或凭据错误 |
| `invalid-request` | Invalid request | `422` | 请求格式或字段校验失败；携带 `errors` 扩展 |
| `internal-error` | Internal server error | `500` | 未预期服务端错误；不暴露内部异常细节 |

| 状态 | 通用含义 | 前端动作 |
| --- | --- | --- |
| `401` | 由 `type` 区分 access token、主账号、refresh 或 VirtualAccount 凭据失败 | 仅 `access-token-invalid` 尝试一次 `/auth/refresh` |
| `403` | 已知文件但当前无权读取 | 从文件视图移除该项目 |
| `404` | 未知资源、不可见目录、无 checkpoint 或未知 validation | 移除对应本地状态，不区分资源存在性 |
| `409` | Request-ID 冲突、进度转移或 checkpoint 不兼容 | 按具体命令刷新状态；仅执行中请求可用原 ID 重试 |
| `412` | 文件 content token 失效 | 刷新 tree version、目录或 metadata 后重试一次 |
| `502` / `503` | 对象存储 URL 生成失败/未配置 | 保留文件目录，显示暂不可用 |

缓存边界：认证响应和 download URL 使用 `no-store`；content URL 使用私有缓存且其 max-age 小于签名 TTL；目录和 metadata 响应使用 `no-store`；version 端点支持 ETag/`If-None-Match`。预签名 URL、refresh cookie 和 access token 不应写入持久化前端状态。

动态文件客户端同时受 `progress.version` 与动态 `tree_version` 影响：validation 成功后不要仅刷新静态 `/files/version`，必须刷新 `/files/d/version` 或直接获取 `/files/d/tree`。

服务端的异常处理器、中间件顺序、命令缓存释放和 Example 恢复路径见 [错误响应与中间件](../architecture/error-response-and-middleware.md)。
