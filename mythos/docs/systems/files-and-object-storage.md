# 静态文件与对象存储系统

## 持久化与 Model

文件发布拥有 `static_file_registrations` 表和 `StaticFileRegistration` Model。每个 `source_locator` 记录稳定对象 key、SHA-256 摘要、媒体类型、尺寸、发布/最后发现时间和退休时间；启动期会完整读取每个 source 并以摘要决定是否覆盖对象。文件字节不在 SQLite 中。

该系统没有专属 Player Interface。静态目录读取依赖已加载的 PlayerInterface 供 access rule 使用；文件 metadata 与 URL 路由使用启动期共享的 `MergedFileTree` 和请求级 `PlayerFileTree`，因此还加载 ArtifactInterface。

## Registry 与数据对象

模块通过 `FileRegistry` 注册 `FileReference` 和 frozen `StaticNodeSpec`，或以 `register_json_tree_asset()` 解析不含手工 version 的严格 JSON manifest。freeze 时将声明转换为 runtime `StaticNode` 并生成 `FileTree`。关键对象：

- `NodeDisplayParams`：文件节点前端标签、描述、语义 icon、排序。
- `ObjectReference`：对象 key、SHA-256 摘要、媒体类型、尺寸；不保存对象存储的 VersionId。bucket versioning 已停用。
- `FileContent`：对象引用、下载名、content token。
- `StaticNode`：文件或目录；`access_rule` 是纯读取函数，必须通过 callback handler 显式声明 PlayerInterface 依赖。
- `MergedFileTree`：freeze 后由静态 FileTree 和 ArtifactNodeTemplate path 构建的共享只读拓扑，资源版本为 `mft1_`。
- `TreeNodeSlot`：Artifact 文件或前置目录的占位节点；请求期以 path resolve 当前玩家实际节点。

启动期 `StaticAssetPublisher` 全量读取新文件或摘要改变的文件，并上传到固定 key `static/<module>/<relative_path>`，再将已解析对象写入 FileTree。mtime 不参与版本计算；`f1_` file ID 只是公开定位符，不是授权凭据；静态 content token 直接使用计算出的 `snv1_` StaticNode version。

## Service 与端点

`FileService` 负责目录授权、metadata 和 RustFS/S3 预签名 URL：

- 静态树：`GET /api/v1/files/ls`、`/s/ls`、`/tree`、`/s/tree`、`/version`。
- 动态树由 `MergedFileTree`、Artifact fruiting 和 FileService 提供：`GET /api/v1/files/d/ls`、`/d/tree`、`/d/version`。动态版本为 `pft4_`，由 `mft1_` 和所需玩家状态版本组成。
- 合并树通用读取：`GET /api/v1/files/{file_id}`、`/{file_id}/{content_token}/content-url`、`/download-url`。

`/files/s/version` 不存在。目录/树枚举跳过 hidden 节点并逐层执行 access rule；已知但无权限文件是 `403`，未知文件或不可见目录是 `404`，旧 content token 是 `412`。

## Example 与重要限制

Example manifest 注册无登录可见的 `/public/README.txt`、`/public/GUEST_ACCESS.txt`，以及仅 Administrator 可见的 `/admin/CONTROL.txt`。Guest 完成 Echo 后通过 Artifact 系统生成 `/archive/ADMIN_ACCESS.txt`。bucket 保持私有且不启用 versioning；对象 key 和摘要由应用管理，不依赖 provider 的 VersionId。已签发 URL 无法因后续账号切换而撤销。完整客户端契约见 [文件 API](../api/files.md)。

相关实现：`registry/files/`、`services/files/`、`services/object_store/service.py`。
