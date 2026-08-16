# File-Storage Specification

## Purpose

提供与实体系统分离的文件存储能力：文件字节按 UUID 落盘、元数据入 SQL 表，并通过 REST 上传、下载与手动删除。

## Requirements

### Requirement: 文件上传

系统 SHALL 提供 `POST /api/files`，接收 raw bytes 请求体；`Content-Type` 记录为媒体类型，可选请求头 `X-Original-Name` 记录原始文件名。服务端 SHALL 生成 `file_id`（UUID），将字节写入 `FILE_DATA_DIR/<file_id>`，计算并持久化 size 与 sha256，返回 `201` 与元数据对象 `{file_id, original_name, media_type, size, sha256, uploaded_by, created_at}`。超过 `MAX_FILE_BYTES` 时 SHALL 返回 `413 FILE_TOO_LARGE`。

#### Scenario: 上传成功

- **WHEN** 已登录用户上传 `text/plain` 字节并附带 `X-Original-Name: readme.txt`
- **THEN** 系统返回 `201`，元数据中 `original_name` 为 `readme.txt`、`size` 与 `sha256` 与实际字节一致，磁盘存在 `FILE_DATA_DIR/<file_id>` 且内容一致

#### Scenario: 超过大小上限

- **WHEN** 已登录用户上传超过 `MAX_FILE_BYTES` 的字节
- **THEN** 系统返回 `413`，错误码为 `FILE_TOO_LARGE`，不产生文件与元数据记录

### Requirement: 文件下载

系统 SHALL 提供 `GET /api/files/:file_id`，返回原始字节流，响应头 `Content-Type` 为记录媒体类型，并附带 `X-Original-Name`、`X-File-Sha256`、`X-File-Size`。文件不存在时 SHALL 返回 `404 FILE_NOT_FOUND`。

#### Scenario: 下载与元数据头一致

- **WHEN** 已登录用户下载存在的文件
- **THEN** 响应字节与上传内容一致，且响应头中的类型、大小、sha256 与上传响应一致

#### Scenario: 文件不存在

- **WHEN** 已登录用户下载不存在的 `file_id`
- **THEN** 系统返回 `404`，错误码为 `FILE_NOT_FOUND`

### Requirement: 手动删除

系统 SHALL 提供 `DELETE /api/files/:file_id`。文件存在时 SHALL 删除 SQL 元数据行与磁盘字节并返回 `204`；文件不存在时 SHALL 返回 `404 FILE_NOT_FOUND`。删除 SHALL 不检查任何实体或历史快照中的引用，允许删除后出现悬空 `file_id`。系统 SHALL NOT 自动清理孤儿文件。

#### Scenario: 删除存在的文件

- **WHEN** 已登录用户删除存在的 `file_id`，无论其是否被实体引用
- **THEN** 系统返回 `204`，files 表中记录与磁盘文件均被移除

#### Scenario: 删除不存在或已删除的文件

- **WHEN** 已登录用户删除不存在的 `file_id`
- **THEN** 系统返回 `404`，错误码为 `FILE_NOT_FOUND`

### Requirement: 文件经 asset 实体接入

`asset` 实体通过其 state 中的 `file_id` 指向 files 表；`media_type` 与文件元数据并存。文件端点 SHALL NOT 感知实体引用结构，实体同步系统 SHALL NOT 校验 `file_id` 是否存在。

#### Scenario: 两系统仅经字段连接

- **WHEN** 上传文件后创建持有该 `file_id` 的 asset 实体
- **THEN** 上传端点不触发任何 WS 同步消息，实体 create 也不要求 files 表存在对应记录

### Requirement: 文件内容不可变

已上传文件的字节 SHALL 不可修改；内容变更通过上传新文件获得新 `file_id` 实现，旧文件保留。

#### Scenario: 内容更新产生新 id

- **WHEN** 用户上传修改后的文本内容
- **THEN** 系统返回新的 `file_id`，旧 `file_id` 的文件内容保持不变

### Requirement: 文件系统与实体同步解耦

上传与下载 SHALL 不改变任何实体的 `revision`/`version`，也 SHALL NOT 向项目 WS 房间广播同步消息；把文件接入实体由实体系统的 `patch`（更新 asset state 的 `file_id`）完成。

#### Scenario: 上传不影响实体版本

- **WHEN** 某项目房间内有连接时用户上传文件
- **THEN** 项目中所有实体 revision 与 version 不变，房间内连接未收到任何 `update`/`created` 消息

### Requirement: 文件端点认证

文件端点 MUST 要求已登录会话；未登录访问 SHALL 返回 `401 UNAUTHORIZED`。

#### Scenario: 未登录被拒绝

- **WHEN** 未携带有效会话 cookie 的请求访问任一文件端点
- **THEN** 系统返回 `401`，错误码为 `UNAUTHORIZED`
