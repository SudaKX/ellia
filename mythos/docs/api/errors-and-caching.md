# API 错误与缓存

| 状态 | 通用含义 | 前端动作 |
| --- | --- | --- |
| `401` | access token 缺失、失效或无效 | 尝试一次 `/auth/refresh`；失败则清空会话 |
| `403` | 已知文件但当前无权读取 | 从文件视图移除该项目 |
| `404` | 未知资源、不可见目录、无 checkpoint 或未知 validation | 移除对应本地状态，不区分资源存在性 |
| `409` | Request-ID 冲突、进度转移或 checkpoint 不兼容 | 按具体命令刷新状态；仅执行中请求可用原 ID 重试 |
| `412` | 文件 content token 失效 | 刷新 tree version、目录或 metadata 后重试一次 |
| `502` / `503` | 对象存储 URL 生成失败/未配置 | 保留文件目录，显示暂不可用 |

缓存边界：认证响应和 download URL 使用 `no-store`；content URL 使用私有缓存且其 max-age 小于签名 TTL；目录和 metadata 响应使用 `no-store`；version 端点支持 ETag/`If-None-Match`。预签名 URL、refresh cookie 和 access token 不应写入持久化前端状态。

动态文件客户端同时受 `progress.version` 与动态 `tree_version` 影响：validation 成功后不要仅刷新静态 `/files/version`，必须刷新 `/files/d/version` 或直接获取 `/files/d/tree`。
