## ADDED Requirements

### Requirement: 文件列表

系统 SHALL 提供 `GET /api/files`，要求已登录会话，返回全部文件元数据的列表，按 `created_at` 降序排列。响应形状 SHALL 为 `{files: FileRecord[]}`，每个元素包含 `{file_id, original_name, media_type, size, sha256, uploaded_by, created_at}`。

#### Scenario: 已登录用户获取文件列表

- **WHEN** 已登录用户请求 `GET /api/files`
- **THEN** 系统返回 `200`，响应为 `{files: [...]}`，元素按 `created_at` 降序，且每个元素字段与上传响应中的元数据字段一致。

#### Scenario: 空文件库

- **WHEN** 已登录用户请求 `GET /api/files` 且后端没有任何文件元数据
- **THEN** 系统返回 `200`，响应为 `{files: []}`。

#### Scenario: 未登录被拒绝

- **WHEN** 未携带有效会话 cookie 的请求访问 `GET /api/files`
- **THEN** 系统返回 `401`，错误码为 `UNAUTHORIZED`。