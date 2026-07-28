# Frontend File Access V1

本文定义前端与 Mythos FileService 配合时的缓存、目录访问、内容预览和下载流程。文件 API 使用 Bearer JWT；前端不得将预签名 URL 写入 LocalStorage、IndexedDB 或持久化状态。

## 1. 版本边界

前端分别维护以下两个版本，不得合并为同一个版本号：

| 版本 | 来源 | 含义 |
| --- | --- | --- |
| `tree_version` | `GET /api/v1/files/version` | 冻结后的静态 FileTree Catalog 版本。目录/文件 Node、路径、revision、展示参数、hidden 状态、下载名、媒体类型和 RustFS 对象版本变化时更新。 |
| `progress.version` | `GET /api/v1/progress` | 当前玩家进度版本。它变化时，文件可见性可能变化。 |

`tree_version` 不包含玩家进度。`progress.version` 不包含静态 FileTree 发布状态。

每个文件还具有 `content_token`，由稳定文件 ID、Node revision 和 RustFS VersionId 派生。它表示该文件当前可读取的静态内容版本。

## 2. API 契约

```text
GET /api/v1/files/version
GET /api/v1/files/ls?path=<absolute virtual path>
GET /api/v1/files/tree?path=<absolute virtual path>
GET /api/v1/files/{file_id}
GET /api/v1/files/{file_id}/{content_token}/content-url
GET /api/v1/files/{file_id}/{content_token}/download-url
GET /api/v1/progress
```

所有请求发送：

```http
Authorization: Bearer <access-token>
```

### 2.1 静态树版本

`GET /files/version` 返回：

```json
{
  "tree_version": "ft1_..."
}
```

响应带有：

```http
Cache-Control: private, no-cache
ETag: "ft1_..."
Vary: Authorization
```

前端保存 ETag，并在后续请求中发送 `If-None-Match`。收到 `304` 时继续使用本地目录缓存；收到 `200` 且 tree version 改变时，丢弃所有本地目录和文件元数据缓存。

### 2.2 目录列表

`GET /files/ls?path=/docs` 返回该目录的直接可见子项：

```json
{
  "path": "/docs",
  "directories": [
    {
      "path": "/docs/notes",
      "display": {"label": "Notes", "description": null, "icon": "folder", "sort_order": 0}
    }
  ],
  "files": [
    {
      "file_id": "f1_...",
      "path": "/docs/guide.txt",
      "revision": "2",
      "media_type": "text/plain; charset=utf-8",
      "size_bytes": 128,
      "content_token": "ct1_...",
      "display": {"label": "Guide", "description": null, "icon": "document", "sort_order": 0}
    }
  ],
  "tree_version": "ft1_..."
}
```

`GET /files/tree?path=/docs` 返回相同 DTO 的嵌套目录树，适合初始化完整文件导航。`ls` 适合按需展开。两者均只返回当前玩家可访问且非 hidden 的子 Node，并允许可访问空目录。前端按目录或子树缓存，每个缓存记录关联的 `tree_version` 和 `progress.version`。

已知路径不在本地缓存中时，直接请求 `GET /files/ls?path=<path>` 或 `GET /files/tree?path=<path>`。隐藏目录同样可以按其完整已知路径直接请求，但不会出现在父目录响应中。返回 `404` 表示目录不存在或对当前玩家不可见；客户端不应尝试区分这两种情况。可访问空目录返回 `200` 与空子项。

### 2.3 文件元数据

`GET /files/{file_id}` 返回文件摘要、`content_token`、摘要、下载名和 `tree_version`。它适用于深链接或目录缓存中已知 `file_id`、但缺少完整元数据的场景。

### 2.4 Content URL

`GET /files/{file_id}/{content_token}/content-url` 返回：

```json
{
  "url": "https://rustfs.example/...",
  "expires_at": "2026-07-27T12:00:00+00:00",
  "content_token": "ct1_..."
}
```

该 JSON 响应使用：

```http
Cache-Control: private, max-age=<content-cache-max-age>, must-revalidate
Vary: Authorization
ETag: "ct1_..."
```

相同 `file_id` 和 `content_token` 会形成相同的 Mythos URL，因此浏览器可直接复用缓存的 JSON 响应和其中的预签名 URL。RustFS 对象响应使用 `private, must-revalidate` 和与签名同步的绝对 `Expires`，浏览器可在 URL 有效期内复用字节，但不会因延迟首个对象请求延长缓存窗口。

`412` 表示 content token 已过期。前端必须刷新 FileTree 版本和相关目录或元数据，再使用新的 token 重试一次。不得使用同一个旧 token 循环重试。

### 2.5 Download URL

`GET /files/{file_id}/{content_token}/download-url` 同样验证 token，但 JSON 响应与 RustFS attachment 响应均使用：

```http
Cache-Control: no-store
```

前端先通过带 Bearer JWT 的 `fetch()` 获取 JSON，再将返回的预签名 URL 交给浏览器导航或下载机制。浏览器导航不会自动携带 Mythos 的 Authorization header，但 RustFS URL 自带下载签名。

## 3. 客户端状态

建议维护以下内存状态：

```text
fileTreeVersion: string | null
fileTreeEtag: string | null
progressVersion: number | null
directoryCache: Map<path, DirectoryListing>
treeCache: Map<path, DirectoryTree>
fileCache: Map<file_id, FileMetadata>
```

目录和文件缓存只在以下二元组匹配时可用：

```text
(fileTreeVersion, progressVersion)
```

预签名 URL 不进入上述应用状态。浏览器 HTTP 缓存负责缓存版本化 content-url 的 JSON 与 RustFS 内容响应。

## 4. 刷新流程

应用启动、页面重新获得焦点或准备显示文件浏览器时：

```text
GET /files/version with If-None-Match
-> GET /progress
-> 比较 tree_version 和 progress.version
-> 任一变化：清空 directoryCache 和 fileCache
-> 请求当前需要展示的目录
```

静态树版本未变但进度版本变化时，仍需重新请求当前目录，因为 access rule 的结果可能变化。

## 5. 打开文件流程

```text
从目录或元数据缓存取得 file_id + content_token
-> GET /files/{file_id}/{content_token}/content-url
-> fetch 返回的 RustFS URL 取得预览内容
```

不要为预签名 URL 额外实现 LocalStorage 缓存。浏览器在相同版本化 content-url 路径和相同 RustFS URL 下自动处理 HTTP 缓存。文件发布后，新的 `content_token` 改变 Mythos URL 路径，旧缓存不会被用于新内容。

## 6. 错误处理

| 状态 | 前端动作 |
| --- | --- |
| `401` | 刷新登录态或跳转认证流程。 |
| `403` | 移除该文件的本地展示状态。 |
| `404` | 移除目录或文件的本地展示状态。 |
| `412` | 刷新 FileTree 版本和关联目录，使用新 token 重试一次。 |
| `502` / `503` | 显示对象存储暂不可用，不清除已知文件目录状态。 |

## 7. 缓存限制

- content URL 是持有者凭据，在签名 TTL 内可直接访问 RustFS。
- 前端刷新 FileTree 只能阻止自身继续请求旧 URL，不能撤销已经签发的 URL。
- 内容 URL 的浏览器缓存期必须短于其签名 TTL。
- download URL 仅用于一次外部下载，不参与浏览器 HTTP 内容缓存。
