# 静态文件与对象存储系统

## 持久化与 Model

文件发布拥有 `static_file_registrations` 表和 `StaticFileRegistration` Model。每个 `source_locator` 记录源文件 mtime、稳定对象 key、对象 VersionId、SHA-256 摘要、媒体类型、尺寸、发布/最后发现时间和退休时间；文件字节不在 SQLite 中。

该系统没有专属 Player Interface。静态目录读取依赖已加载的 `ProgressInterface` 供 access rule 使用；文件 metadata 与 URL 路由使用合并后的玩家树，因此还加载 ArtifactInterface。

## Registry 与数据对象

模块通过 `FileRegistry` 注册 `FileReference` 和 `StaticNode`，或以 `register_json_tree_asset()` 解析严格 JSON manifest。冻结生成 `FileTree`。关键对象：

- `DisplayParams`：前端标签、描述、语义 icon、排序。
- `ObjectReference`：对象 key、VersionId、摘要、媒体类型、尺寸。
- `FileContent`：对象引用、下载名、content token。
- `StaticNode`：文件或目录；`access_rule` 是纯读取函数。

启动期 `StaticAssetPublisher` 仅上传新文件或 mtime 改变的文件到 `static/<module>/<relative_path>`，再将已解析对象写入 FileTree。`f1_` file ID 只是公开定位符，不是授权凭据；静态 content token 使用 `ct1_`。

## Service 与端点

`FileService` 负责目录授权、metadata 和 RustFS/S3 预签名 URL：

- 静态树：`GET /api/v1/files/ls`、`/s/ls`、`/tree`、`/s/tree`、`/version`。
- 动态树由 Artifact 系统提供：`GET /api/v1/files/d/ls`、`/d/tree`、`/d/version`。
- 合并树通用读取：`GET /api/v1/files/{file_id}`、`/{file_id}/{content_token}/content-url`、`/download-url`。

`/files/s/version` 不存在。目录/树枚举跳过 hidden 节点并逐层执行 access rule；已知但无权限文件是 `403`，未知文件或不可见目录是 `404`，旧 content token 是 `412`。

## Example 与重要限制

Example manifest 注册 `/public/README.txt` 与受 completed 规则保护的 `/archive/result.txt`。对象存储必须启用 versioning 并返回 VersionId；bucket 保持私有。已签发 URL 无法因后续进度变化而撤销。完整客户端契约见 [文件 API](../api/files.md)。

相关实现：`registry/files/`、`services/files/`、`services/object_store/service.py`。
