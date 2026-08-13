# 文件 API

## 树类型与端点

所有端点均要求 Bearer token。静态树只含启动期冻结的文件；动态树遍历启动期 `MergedFileTree`，并将当前玩家 Artifact fruiting 到对应 Slot。`/files/tree` 和 `/files/s/tree` 等价，`/files/s/version` 不存在。

| 方法 | 路径 | 树 |
| --- | --- | --- |
| GET | `/api/v1/files/ls?path=/`、`/s/ls` | 静态目录直接子项 |
| GET | `/api/v1/files/tree?path=/`、`/s/tree` | 静态递归树 |
| GET | `/api/v1/files/version` | 静态 tree version |
| GET | `/api/v1/files/d/ls?path=/` | 动态目录直接子项 |
| GET | `/api/v1/files/d/tree?path=/` | 动态递归树 |
| GET | `/api/v1/files/d/version` | 动态 tree version |
| GET | `/api/v1/files/{file_id}` | 合并树 metadata |
| GET | `/api/v1/files/{file_id}/{content_token}/content-url` | inline 预签名 URL |
| GET | `/api/v1/files/{file_id}/{content_token}/download-url` | attachment 预签名 URL |

目录和树响应都包含 `path`、`directories`、`files` 与 `tree_version`。文件摘要为：

```json
{
  "file_id":"f1_...","path":"/archive/ADMIN_ACCESS.txt","version":"antv2_...",
  "media_type":"text/plain; charset=utf-8","size_bytes":96,
  "content_token":"act3_...",
  "display":{"label":"ADMIN_ACCESS.txt","description":"Administrator credentials","icon":"document","sort_order":1}
}
```

metadata 额外返回 `content_digest`、`download_name` 和合并树 `tree_version`。静态 token 直接使用 StaticNode 的 `snv1_` version；Artifact token 使用绑定玩家、Artifact ID 和 Node ID 的 `act3_`；两者均为内容前置条件，不是授权凭据。

## 预签名 URL、缓存和错误

content URL 响应为 `{url, expires_at, content_token}`，带 `ETag`（token）、`Vary: Authorization` 与私有、可重新验证缓存策略。download URL 使用 `no-store`。前端先使用 Bearer 调 Mythos，再以返回 URL 直接读取 RustFS/S3；不要把 URL 持久化。

`/version` 与 `/d/version` 支持 `If-None-Match`，命中返回 `304`。动态 tree version 为 `pft4_`，是 `MergedFileTree.resource_version`（`mft1_`）、ArtifactInterface.version 和文件 access_rule 显式声明的 PlayerInterface 状态版本的不透明组合；静态 tree version 不包含 Artifact。

动态文件 access_rule 的依赖 mask 进入 callback ID。账号或进度变化可能使 `/files/d/version` 返回新的 ETag，即使静态拓扑没有变化；没有声明依赖的 credits 或 hints 变化不会无条件改变 `pft4_`。动态读取仍然每次重新执行 hidden、路径链 access_rule 和 content-token 校验。静态文件 access rule 的当前支持范围见 [文件系统](../systems/files-and-object-storage.md)。

| 状态 | 含义与动作 |
| --- | --- |
| `403` | 已知文件无访问权限；移除本地文件状态 |
| `404` | 文件未知，或目录不可见；移除相应缓存 |
| `412` | content token 已过期；刷新对应 tree/version 后仅重试一次 |
| `502` / `503` | 对象存储 URL 签发失败；保留目录状态并提示暂不可用 |

Example 页面使用 `/files/d/version` 与 `/files/d/tree`。内部模型和授权规则见 [文件系统](../systems/files-and-object-storage.md) 与 [Artifact 系统](../systems/artifacts-and-dynamic-files.md)。
