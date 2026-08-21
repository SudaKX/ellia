## ADDED Requirements

### Requirement: 清除在场位置

系统 SHALL 支持客户端发送 `focus` 消息且 `entity_id` 为 `null`，用于清除当前连接记录的用户焦点。清除后 SHALL 从内存中移除该连接的 focus，并向房间广播更新后的 `presence`；其他用户不再看到该用户位于任何实体或字段。

#### Scenario: 清除当前焦点

- **WHEN** 已上报 focus 的客户端发送 `{type:"focus", entity_id:null}`
- **THEN** 服务端清除该连接的 focus，房间收到新的 `presence` 列表且不包含该用户的 `entity_id`/`data_path`。

#### Scenario: 未上报焦点时清除无副作用

- **WHEN** 没有任何 focus 记录的连接发送 `{type:"focus", entity_id:null}`
- **THEN** 服务端不报错，房间广播当前 presence，该连接仍可继续收发消息。

### Requirement: 操作确认消息携带 ref

系统 SHALL 在客户端请求携带 `ref` 时，将 `ref` 回传在对应的服务端确认/广播消息中。涉及消息 SHALL 包括 `locked`、`unlocked`、`deleted`、`rolled_back`；客户端 `unlock` 消息 SHALL 也接受可选 `ref`。`ref` 仅用于发起请求的客户端进行响应匹配，其他客户端收到后可忽略。

#### Scenario: 锁成功附带 ref

- **WHEN** 客户端发送 `{type:"lock", ref:"r1", entity_id:"e1", data_path:"e1@state:/display/label"}`
- **THEN** 服务端广播 `locked` 消息并包含 `ref:"r1"`、该锁的 `entity_id`、`data_path` 与持有者。

#### Scenario: 解锁成功附带 ref

- **WHEN** 客户端发送 `{type:"unlock", ref:"r2", entity_id:"e1", data_path:"e1@state:/display/label"}`
- **THEN** 服务端释放锁并广播 `unlocked` 消息且包含 `ref:"r2"`。

#### Scenario: 删除成功附带 ref

- **WHEN** 客户端发送 `{type:"delete", ref:"r3", entity_id:"e1"}`
- **THEN** 服务端删除实体并广播 `deleted` 消息，消息中包含 `ref:"r3"`。

#### Scenario: 回退成功附带 ref

- **WHEN** 客户端发送 `{type:"rollback", ref:"r4", entity_id:"e1"}`
- **THEN** 服务端回退后广播 `rolled_back` 消息，消息中包含 `ref:"r4"`。

### Requirement: 错误消息继续携带 ref

系统 SHALL 在扩展后的确认消息涉及的请求失败时，继续按现有错误契约返回 `error {ref, code, message}`；新增 `ref` 字段不得改变错误码集合。

#### Scenario: 清除非法焦点返回错误

- **WHEN** 客户端发送 `{type:"focus", entity_id:null}` 以外的非法 focus 请求
- **THEN** 服务端返回 `error`，错误码为 `VALIDATION`，且不改变其他连接可见的 presence。