## MODIFIED Requirements

### Requirement: file-tree 与 dag 容器

`file-tree` kind 的 state SHALL 为 `{rootId, nodes}`，其中 `nodes` 为 `TreeNodeId → FileTreeNode` 的扁平节点表，`FileTreeNode` SHALL 包含 `id/name/isDirectory/inode/parent/order`。`isDirectory=true` 的节点 SHALL 将 `inode` 置为 `null`，且可作为父节点；`isDirectory=false` 的节点 SHALL 指定非空 `inode` 引用已有 `file-node`/`artifact-node` 实体，且 SHALL NOT 作为任何节点的父节点。同级节点的 `name` SHALL 唯一；非根节点 SHALL 指定 `parent`；根节点 SHALL 为 `isDirectory=true`、`name="/"`、`inode=null`、`parent=null`。`dag` kind 的 state SHALL 为 `{entryIds, nodes}`，其中 `nodes` 为 `DagNodeId → DagNode` 的扁平节点表，`DagNode` SHALL 包含 `id/name/pnode/successors`。`name` 为非空字符串；`pnode` 为引用 `progress-node` 实体的 entity id，可为 `null`；`successors` 为有序后继 `DagNodeId` 列表，且每个后继必须存在于 `nodes`；`entryIds` 必须引用已存在的 `DagNodeId`。`file-node` state SHALL NOT 包含 parent 挂接字段；`progress-node` state SHALL NOT 包含 `successors` 或 `is_entry` 字段。系统 SHALL NOT 强制容器数量，也 SHALL NOT 校验 `inode`/`pnode` 引用的实体是否存在（允许悬空）。

#### Scenario: 创建文件树容器

- **WHEN** 客户端发送 `create {kind:"file-tree", ui_kind:"file-tree", resource_id:"file-tree:main", state:{rootId:"root", nodes:{root:{id:"root",name:"/",isDirectory:true,inode:null,parent:null,order:0}}}}`
- **THEN** 创建成功，revision 与 version 均为 1

#### Scenario: 文件夹不允许携带 inode

- **WHEN** 客户端创建 file-tree，其中某个 `isDirectory:true` 节点的 `inode` 不为 `null`
- **THEN** 服务端返回 `error {code: "VALIDATION"}`，不创建实体

#### Scenario: 文件节点必须携带 inode

- **WHEN** 客户端创建 file-tree，其中某个 `isDirectory:false` 节点缺少 `inode` 或 `inode` 为空
- **THEN** 服务端返回 `error {code: "VALIDATION"}`，不创建实体

#### Scenario: 文件节点不能包含子节点

- **WHEN** 客户端创建 file-tree，其中某个 `isDirectory:false` 节点被其他节点作为 `parent`
- **THEN** 服务端返回 `error {code: "VALIDATION"}`，不创建实体

#### Scenario: 同级节点名称重复被拒绝

- **WHEN** 客户端创建 file-tree，其中同一 `parent` 下存在两个 `name` 相同的节点
- **THEN** 服务端返回 `error {code: "VALIDATION"}`，不创建实体

#### Scenario: 非根节点缺少 parent 被拒绝

- **WHEN** 客户端创建 file-tree，其中非根节点的 `parent` 为 `null`
- **THEN** 服务端返回 `error {code: "VALIDATION"}`，不创建实体

#### Scenario: 节点不携带拓扑

- **WHEN** 客户端发送不含 parent 字段的 `file-node` 创建请求，或发送不含 `successors`/`is_entry` 的 `progress-node` 创建请求
- **THEN** 创建成功；树结构只能通过 file-tree 的 `nodes` 表达，DAG 拓扑只能通过 dag 的 `nodes`/`entryIds` 表达

#### Scenario: 内部拓扑引用必须存在

- **WHEN** 客户端发送 `dag` 的 create，其 `successors` 或 `entryIds` 引用了不存在的 `DagNodeId`
- **THEN** 服务端返回 `error {code: "VALIDATION"}`，不创建实体

#### Scenario: DAG 节点缺少 name 被拒绝

- **WHEN** 客户端发送 `dag` 的 create，其中某个 `DagNode` 的 `name` 为空
- **THEN** 服务端返回 `error {code: "VALIDATION"}`，不创建实体

#### Scenario: 外部实体引用允许悬空

- **WHEN** 客户端发送 `dag` 的 create，其 `pnode` 引用了不存在的 progress-node 实体，或 file-tree 的 `inode` 引用了不存在的实体
- **THEN** 创建成功，不要求被引用实体已存在
