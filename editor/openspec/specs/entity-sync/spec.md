# Entity-Sync Specification

## Purpose

定义谜题模块实体的权威数据模型、实体历史快照、WS v2 同步协议以及字段锁与在场机制，作为多人在线编辑的后端权威状态源。

## Requirements

### Requirement: WS 连接认证与项目房间

系统 SHALL 在 `/ws/projects/:id` 升级握手时校验 cookie 会话；未登录 SHALL 拒绝升级，项目不存在 SHALL 拒绝升级。同一项目内的连接组成项目房间，服务端 SHALL 向房间内其他连接广播同步消息。

#### Scenario: 合法会话接入房间

- **WHEN** 携带有效会话 cookie 的客户端连接已存在项目的 WS 地址
- **THEN** 连接建立，服务端发送 `hello`，其中 `protocol_version` 为 `2`

#### Scenario: 未登录拒绝升级

- **WHEN** 无有效会话 cookie 的客户端请求升级到项目 WS 地址
- **THEN** 升级被拒绝，连接未建立

#### Scenario: 项目不存在拒绝升级

- **WHEN** 已登录客户端请求不存在的项目 id 的 WS 地址
- **THEN** 升级被拒绝，连接未建立

### Requirement: join 与全量重连同步

客户端 SHALL 可发送 `join {project_id, vector}`，其中 vector 为 `{entity_id: revision}`。服务端 SHALL 回复 `sync`：对本地 vector 中不存在或 revision 不一致的存活实体发送全量 `EntityRecord`；对 vector 中存在但数据库已不存在的实体 id 归入 `removed_ids`；revision 完全一致的实体不发送。系统 SHALL NOT 提供增量重放。

#### Scenario: 部分实体需要同步

- **WHEN** 客户端以 `{e1: 2, e2: 3, gone: 1}` 加入，服务端当前 `e1` revision 为 2、`e2` revision 为 5、`gone` 已删除
- **THEN** 服务端返回 `sync`，其中 `entities` 仅含 `e2` 的全量记录，`removed_ids` 含 `gone`，且不含 `e1`

#### Scenario: 空向量全量拉取

- **WHEN** 新客户端以空 vector 加入
- **THEN** 服务端返回 `sync`，其中 `entities` 包含项目内全部存活实体

### Requirement: 实体数据形状与创建校验

`EntityRecord` SHALL 包含 `id`、`group`、`kind`、`ui_kind`、`resource_id`、`revision`、`version`、`state`。创建实体时 `kind` MUST 属于共享包 16 种 `ENTITY_KINDS`；`ui_kind` MUST 显式提供且属于该 kind 的允许值；`resource_id` MUST 形如 `<namespace>:<id>`，前缀与 kind 的命名空间一致，完整字符串在项目内唯一。

#### Scenario: 合法创建

- **WHEN** 客户端发送 `create {group:"main", kind:"hint", ui_kind:"form", resource_id:"stable-id:hint-1", state:{...}}`
- **THEN** 服务端持久化实体，`revision` 与 `version` 均为 1，向提交者发送 `created`（含其 `ref`），并向房间广播 `created`

#### Scenario: ui_kind 缺省或与 kind 不匹配

- **WHEN** 客户端发送未携带 `ui_kind` 的 `create`，或携带的 `ui_kind` 不属于该 kind 允许值
- **THEN** 服务端返回 `error {code: "VALIDATION"}`，不创建实体

#### Scenario: resource_id 非法或重复

- **WHEN** 客户端发送前缀与 kind 不匹配、id 部分含 `:` 或空白的 `resource_id`，或完整 `resource_id` 与项目内已有实体相同
- **THEN** 服务端分别返回 `error {code: "VALIDATION"}` 或 `error {code: "RESOURCE_CONFLICT"}`，不创建实体

### Requirement: asset 与文件引用关系

`asset` kind 的 state SHALL 为 `{file_id, media_type}`；其 resource_id 的 id 部分 MUST 是规范相对路径（非空、不以 `/` 开头、不含 `\` 与 `:`、无 `.`/`..` 路径段），前缀为 `asset-path`。系统 SHALL NOT 校验 `file_id` 是否存在于 files 表（允许悬空引用），也 SHALL NOT 限制多个 asset 引用同一个 `file_id`（允许复用同一份字节）。

#### Scenario: 创建 asset 允许悬空 file_id

- **WHEN** 客户端发送 `create {kind:"asset", ui_kind:"asset", resource_id:"asset-path:assets/public/a.txt", state:{file_id:"<任意UUID>", media_type:"text/plain"}}`，而 files 表中没有该 file_id
- **THEN** 创建成功，`revision` 与 `version` 均为 1

#### Scenario: 多个 asset 复用同一 file_id

- **WHEN** 客户端先后创建两个 asset，其 state 中的 `file_id` 相同
- **THEN** 两个 asset 均创建成功，系统不进行去重或独占校验

#### Scenario: asset-path 路径非法

- **WHEN** 客户端发送 resource_id 为 `asset-path:../a.txt` 或含 `\`、`:` 的 create
- **THEN** 服务端返回 `error {code: "VALIDATION"}`，不创建实体

### Requirement: file-tree 与 progress-dag 容器

`file-tree` kind 的 state SHALL 为 `{root_stable_id, children}`，其中 `children` 为 `parent stable_id → 有序 child stable_id 列表` 的映射；`progress-dag` kind 的 state SHALL 为 `{entry_stable_ids, successors}`，其中 `successors` 为 `from stable_id → 有序 to stable_id 列表` 的映射。`file-tree-node` state SHALL NOT 包含 parent 挂接字段；`progress-node` state SHALL NOT 包含 `successors` 或 `is_entry` 字段。系统 SHALL NOT 强制容器数量，也 SHALL NOT 校验拓扑中引用的 stable_id 是否存在（允许悬空）。

#### Scenario: 创建文件树容器

- **WHEN** 客户端发送 `create {kind:"file-tree", ui_kind:"file-tree", resource_id:"file-tree:main", state:{root_stable_id:null, children:{}}}`
- **THEN** 创建成功，revision 与 version 均为 1

#### Scenario: 节点不携带拓扑

- **WHEN** 客户端发送不含 parent 字段的 `file-tree-node` 创建请求，或发送不含 `successors`/`is_entry` 的 `progress-node` 创建请求
- **THEN** 创建成功；树结构只能通过 file-tree 的 `children` 表达，DAG 拓扑只能通过 progress-dag 的 `successors`/`entry_stable_ids` 表达

#### Scenario: 拓扑引用允许悬空

- **WHEN** 客户端发送 `progress-dag` 的 create，其 `successors`/`entry_stable_ids` 引用了不存在的 stable_id
- **THEN** 创建成功，不要求被引用节点已存在

### Requirement: 字段锁

服务端 SHALL 维护内存态字段锁，锁键为 data_path，格式 `<entity_id>@<root>:<json_path>`，其中 root 为 `state`、`group` 或 `resource_id`；`group` 与 `resource_id` 的 json_path 为空。`state` 的 json_path 使用 JSON Pointer，叶子标量字段与整个数组/对象均可作为锁单元。每连接最多持有一把锁；同一连接对同一路径重复 lock 幂等成功；同一连接对新路径 lock 时自动释放旧锁；其他连接持有锁时 SHALL 返回 `lock_denied` 并附持有者信息。

#### Scenario: 他人持有锁

- **WHEN** 连接 B 对已被连接 A 锁定的 data_path 发送 `lock`
- **THEN** 服务端返回 `lock_denied`，包含持有者 `{user_id, username}`，连接 B 未获得锁

#### Scenario: 锁替换与断线清理

- **WHEN** 连接 A 已锁定路径 P 后对路径 Q 发送 `lock`，随后连接 A 断开
- **THEN** 路径 Q 加锁成功且路径 P 被释放；连接断开后其全部锁被清除，其他连接可锁定 P 与 Q

### Requirement: patch 与增量广播

客户端 SHALL 通过 `patch {ref, entity_id, data_path, value}` 修改已锁定的路径。服务端 MUST 校验锁持有者为当前连接，否则返回 `error STALE_LOCK`。成功应用后 SHALL：将更新前的 state 写入历史快照、`revision` 与 `version` 各加 1、向提交者发送 `applied`、向房间其他连接广播 `update`（含 data_path 与新 value）、释放该锁并广播 `unlocked`。

#### Scenario: 持有锁时成功修改

- **WHEN** 连接 A 锁定 `e1@state:/display/label` 后发送 `patch` 将值改为 `"新标签"`
- **THEN** 服务端返回 `applied`（revision 与 version 均比修改前大 1），连接 B 收到 `update`，随后收到 `unlocked`

#### Scenario: 未持锁提交

- **WHEN** 连接 A 未锁定路径即发送 `patch`
- **THEN** 服务端返回 `error {code: "STALE_LOCK"}`，实体状态不变

### Requirement: group 与 resource_id 的 patch 规则

通过 patch 修改 `@group:` 时新值 MUST 匹配 `^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$`；修改 `@resource_id:` 时新值 MUST 保持与 kind 一致的命名空间前缀，且完整字符串在项目内唯一。

#### Scenario: group 合法修改

- **WHEN** 客户端锁定 `e1@group:` 并 patch 为 `"chapter1"`
- **THEN** 修改成功并按普通 patch 规则递增双计数器与广播

#### Scenario: resource_id 跨命名空间或重复被拒绝

- **WHEN** 客户端锁定 `e1@resource_id:` 后 patch 为不同命名空间前缀的值，或项目内已存在的完整 resource_id
- **THEN** 服务端返回 `error {code: "VALIDATION"}` 或 `error {code: "RESOURCE_CONFLICT"}`，原 resource_id 不变

### Requirement: 实体历史快照与回退

系统 SHALL 在每次非回退更新前，将更新前的 state 与当时的 version 存入实体历史；历史超过上限 N 时删除最旧快照。`rollback` SHALL 应用 `version - 1` 对应的快照并删除该快照行，随后 `version` 减 1、`revision` 加 1，向房间广播 `rolled_back`（携带全量新 state）。回退不可逆：被消费的快照不再恢复。

#### Scenario: 回退成功且 revision 单调

- **WHEN** 实体 revision 为 3、version 为 3 且有 version 2 快照时客户端发送 `rollback`
- **THEN** 实体 state 变为 version 2 快照的内容，`version` 变为 2、`revision` 变为 4，提交者收到 `rolled_back`，房间其他连接收到 `rolled_back` 且能按 revision 4 应用

#### Scenario: 无历史可回退

- **WHEN** 实体 `version` 为 1（无历史快照）时客户端发送 `rollback`
- **THEN** 服务端返回 `error {code: "HISTORY_EMPTY"}`，实体不变

#### Scenario: 历史超过 N 被修剪

- **WHEN** 历史上限 N 为 20 且实体完成第 21 次非回退更新
- **THEN** 该实体历史快照数不超过 20，最旧快照已被删除

### Requirement: 实体物理删除

`delete` SHALL 物理删除实体行并级联清除其历史；若其他连接持有该实体任意字段锁，SHALL 返回 `error ENTITY_LOCKED` 并附持有者。删除成功后服务端 SHALL 向提交者与房间广播 `deleted {entity_id}`。被删除实体的 resource_id 可被重新创建使用。

#### Scenario: 删除与广播

- **WHEN** 客户端对无他人锁的实体发送 `delete`
- **THEN** 实体及其历史被移除，房间收到 `deleted {entity_id}`，后续 `patch` 该实体返回 `error ENTITY_NOT_FOUND`

#### Scenario: 他人锁定实体时删除被拒绝

- **WHEN** 连接 B 持有实体任一字段锁时连接 A 发送 `delete`
- **THEN** 服务端返回 `error {code: "ENTITY_LOCKED"}` 并附持有者，实体保留

### Requirement: history 查询

客户端 SHALL 可通过 `history {ref, entity_id}` 获取该实体全部历史快照；服务端 SHALL 返回 `history {ref, entity_id, entries}`，entries 按 version 降序，每项包含 `version`、`state`、`author_id`、`created_at`。

#### Scenario: 查询历史

- **WHEN** 客户端对存在 3 条快照的实体发送 `history`
- **THEN** 服务端返回 `history`，entries 长度为 3 且按 version 降序

### Requirement: focus 与 presence

客户端 SHALL 可通过 `focus {entity_id, data_path?}` 上报当前所在位置。服务端 SHALL 在成员列表或 focus 变化时广播 `presence`，其中每个用户携带 `{id, username, entity_id?, data_path?}`；连接断开时 SHALL 清除该连接 focus 并广播新 presence。focus 仅存内存，不持久化。

#### Scenario: 位置变化广播

- **WHEN** 连接 A 发送 `focus {entity_id: "e1", data_path: "e1@state:/display/label"}`
- **THEN** 房间内连接收到 `presence`，用户 A 的条目包含 `entity_id: "e1"` 与对应 data_path

#### Scenario: 断开清除位置

- **WHEN** 已上报 focus 的连接断开
- **THEN** 服务端广播不含该连接的 presence，且其 focus 记录被移除

### Requirement: 心跳与错误契约

系统 SHALL 支持 `ping`/`pong` 心跳。对任何失败请求 SHALL 返回 `error {ref?, code, message}`，其中 `ref` 在请求携带时原样回传。错误码集合 SHALL 至少包含 `BAD_JSON`、`UNAUTHORIZED`、`PROJECT_NOT_FOUND`、`ENTITY_NOT_FOUND`、`VALIDATION`、`RESOURCE_CONFLICT`、`STALE_LOCK`、`LOCK_DENIED`、`ENTITY_LOCKED`、`HISTORY_EMPTY`。

#### Scenario: 非法 JSON 消息

- **WHEN** 连接发送无法解析为 JSON 的数据
- **THEN** 服务端返回 `error {code: "BAD_JSON"}`

#### Scenario: 请求失败回传 ref

- **WHEN** 客户端发送带 `ref: "r1"` 的 `history`，目标实体不存在
- **THEN** 服务端返回 `error {ref: "r1", code: "ENTITY_NOT_FOUND"}`

### Requirement: 清除在场位置

系统 SHALL 支持客户端发送 `focus` 消息且 `entity_id` 为 `null`，用于清除当前连接记录的用户焦点。清除后 SHALL 从内存中移除该连接的 focus，并向房间广播更新后的 `presence`；其他用户不再看到该用户位于任何实体或字段。

#### Scenario: 清除当前焦点

- **WHEN** 已上报 focus 的客户端发送 `{type:"focus", entity_id:null}`
- **THEN** 服务端清除该连接的 focus，房间收到新的 `presence` 列表且不包含该用户的 `entity_id`/`data_path`

#### Scenario: 未上报焦点时清除无副作用

- **WHEN** 没有任何 focus 记录的连接发送 `{type:"focus", entity_id:null}`
- **THEN** 服务端不报错，房间广播当前 presence，该连接仍可继续收发消息

### Requirement: 操作确认消息携带 ref

系统 SHALL 在客户端请求携带 `ref` 时，将 `ref` 回传在对应的服务端确认/广播消息中。涉及消息 SHALL 包括 `locked`、`unlocked`、`deleted`、`rolled_back`；客户端 `unlock` 消息 SHALL 也接受可选 `ref`。`ref` 仅用于发起请求的客户端进行响应匹配，其他客户端收到后可忽略。

#### Scenario: 锁成功附带 ref

- **WHEN** 客户端发送 `{type:"lock", ref:"r1", entity_id:"e1", data_path:"e1@state:/display/label"}`
- **THEN** 服务端广播 `locked` 消息并包含 `ref:"r1"`、该锁的 `entity_id`、`data_path` 与持有者

#### Scenario: 解锁成功附带 ref

- **WHEN** 客户端发送 `{type:"unlock", ref:"r2", entity_id:"e1", data_path:"e1@state:/display/label"}`
- **THEN** 服务端释放锁并广播 `unlocked` 消息且包含 `ref:"r2"`

#### Scenario: 删除成功附带 ref

- **WHEN** 客户端发送 `{type:"delete", ref:"r3", entity_id:"e1"}`
- **THEN** 服务端删除实体并广播 `deleted` 消息，消息中包含 `ref:"r3"`

#### Scenario: 回退成功附带 ref

- **WHEN** 客户端发送 `{type:"rollback", ref:"r4", entity_id:"e1"}`
- **THEN** 服务端回退后广播 `rolled_back` 消息，消息中包含 `ref:"r4"`

### Requirement: 错误消息继续携带 ref

系统 SHALL 在扩展后的确认消息涉及的请求失败时，继续按现有错误契约返回 `error {ref, code, message}`；新增 `ref` 字段不得改变错误码集合。

#### Scenario: 清除非法焦点返回错误

- **WHEN** 客户端发送 `{type:"focus", entity_id:null}` 以外的非法 focus 请求
- **THEN** 服务端返回 `error`，错误码为 `VALIDATION`，且不改变其他连接可见的 presence
