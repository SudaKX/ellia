## MODIFIED Requirements

### Requirement: 实体数据形状与创建校验

`EntityRecord` SHALL 包含 `id`、`group`、`kind`、`ui_kind`、`resource_id`、`revision`、`version`、`state`、`comment`。创建实体时 `kind` MUST 属于共享包 16 种 `ENTITY_KINDS`；`ui_kind` MUST 显式提供且属于该 kind 的允许值；`resource_id` MUST 形如 `<namespace>:<id>`，前缀与 kind 的命名空间一致，完整字符串在项目内唯一。`create` 消息 SHALL 支持可选 `comment` 字段，缺省为空字符串。

#### Scenario: 合法创建

- **WHEN** 客户端发送 `create {group:"main", kind:"hint", ui_kind:"form", resource_id:"stable-id:hint-1", state:{...}, comment:"提示文件"}`
- **THEN** 服务端持久化实体，`revision` 与 `version` 均为 1，`comment` 为 `"提示文件"`，向提交者发送 `created`（含其 `ref`），并向房间广播 `created`

#### Scenario: 创建时未提供 comment

- **WHEN** 客户端发送不携带 `comment` 字段的 `create`
- **THEN** 服务端持久化实体且 `comment` 为空字符串

#### Scenario: ui_kind 缺省或与 kind 不匹配

- **WHEN** 客户端发送未携带 `ui_kind` 的 `create`，或携带的 `ui_kind` 不属于该 kind 允许值
- **THEN** 服务端返回 `error {code: "VALIDATION"}`，不创建实体

#### Scenario: resource_id 非法或重复

- **WHEN** 客户端发送前缀与 kind 不匹配、id 部分含 `:` 或空白的 `resource_id`，或完整 `resource_id` 与项目内已有实体相同
- **THEN** 服务端分别返回 `error {code: "VALIDATION"}` 或 `error {code: "RESOURCE_CONFLICT"}`，不创建实体

### Requirement: 字段锁

服务端 SHALL 维护内存态字段锁，锁键为 data_path，格式 `<entity_id>@<root>:<json_path>`，其中 root 为 `state`、`group`、`resource_id` 或 `comment`；`group`、`resource_id` 与 `comment` 的 json_path 为空。`state` 的 json_path 使用 JSON Pointer，叶子标量字段与整个数组/对象均可作为锁单元。每连接最多持有一把锁；同一连接对同一路径重复 lock 幂等成功；同一连接对新路径 lock 时自动释放旧锁；其他连接持有锁时 SHALL 返回 `lock_denied` 并附持有者信息。

#### Scenario: 他人持有锁

- **WHEN** 连接 B 对已被连接 A 锁定的 data_path 发送 `lock`
- **THEN** 服务端返回 `lock_denied`，包含持有者 `{user_id, username}`，连接 B 未获得锁

#### Scenario: 锁替换与断线清理

- **WHEN** 连接 A 已锁定路径 P 后对路径 Q 发送 `lock`，随后连接 A 断开
- **THEN** 路径 Q 加锁成功且路径 P 被释放；连接断开后其全部锁被清除，其他连接可锁定 P 与 Q

#### Scenario: 锁定 comment 路径

- **WHEN** 连接 A 锁定 `e1@comment:`
- **THEN** 锁成功，其他连接锁定同一路径返回 `lock_denied`

### Requirement: group、resource_id 与 comment 的 patch 规则

通过 patch 修改 `@group:` 时新值 MUST 匹配 `^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$`；修改 `@resource_id:` 时新值 MUST 保持与 kind 一致的命名空间前缀，且完整字符串在项目内唯一；修改 `@comment:` 时新值 MUST 为字符串，允许任意内容。

#### Scenario: group 合法修改

- **WHEN** 客户端锁定 `e1@group:` 并 patch 为 `"chapter1"`
- **THEN** 修改成功并按普通 patch 规则递增双计数器与广播

#### Scenario: resource_id 跨命名空间或重复被拒绝

- **WHEN** 客户端锁定 `e1@resource_id:` 后 patch 为不同命名空间前缀的值，或项目内已存在的完整 resource_id
- **THEN** 服务端返回 `error {code: "VALIDATION"}` 或 `error {code: "RESOURCE_CONFLICT"}`，原 resource_id 不变

#### Scenario: 修改 comment

- **WHEN** 客户端锁定 `e1@comment:` 后 patch 为 `"新注释"`
- **THEN** 修改成功，实体 `comment` 更新为 `"新注释"`，按普通 patch 规则广播 `update`

#### Scenario: comment 非字符串被拒绝

- **WHEN** 客户端锁定 `e1@comment:` 后 patch 为非字符串值（如数字或对象）
- **THEN** 服务端返回 `error {code: "VALIDATION"}`，comment 不变