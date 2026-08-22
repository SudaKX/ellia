## Context

file-tree 编辑器需要在现有 WS v2 同步、字段锁、实体 store 基础上，提供直观的树拓扑编辑。由于 file-tree 是容器实体，节点数据与实体数据分离，需要独立的树内节点模型。

## Goals / Non-Goals

**Goals:**
- 用扁平节点表支持直接 UUID data_path 锁与 patch，避免深层 JSON Pointer
- 明确文件夹/文件语义，减少歧义
- 添加节点只引用已有 inode 实体，不在树编辑器中重复维护 artifact/node_generator
- 删除树节点不级联删除 inode 实体
- 协同删除时按记录路径回退，不依赖旧数据快照

**Non-Goals:**
- 不做 file-tree 的拖拽排序（当前用 order 字段预留）
- 不做 artifact-node 创建表单的深度集成
- 不做导出器实现

## Decisions

### D1: 扁平节点表 + 直接 UUID 寻址

`FileTreeState` 使用 `{rootId, nodes}`，`nodes` 是 `TreeNodeId → FileTreeNode` 的扁平表。

- **理由**：锁和 patch 可直接使用 `@state:/nodes/<treeNodeId>`，无需 `/root/children/...` 长路径；删除子树通过遍历后代逐个 `removeField`。
- **替代方案**：嵌套递归树。被否：删除子树需要深层路径，锁与同步路径更长。

### D2: 显式 isDirectory

`FileTreeNode` 增加 `isDirectory` 布尔字段。

- 文件夹：`inode` 必须为 `null`，可以有 children
- 文件：`inode` 必须引用已有 `file-node`/`artifact-node`，不能有 children
- **理由**：不再依赖 inode 实体内容推导类型，树拓扑自描述。

### D3: inode 只引用现有实体

添加/编辑节点时，`inode` 通过 `EntityReferenceSelect`（namespace `inode`、`value-as-id`）选择已有实体。

- **理由**：与 FormEditor ref 字段行为一致；artifact 与 node_generator 已经记录在 artifact-node 实体上，不需要在 file-tree 重复。

### D4: 路径段回退

记录当前选中节点的路径段；节点被删除时从根开始按路径段逐级查找，回退到第一个仍存在的路径。

- **理由**：不依赖旧数据快照，避免 `entitiesStore` 原地修改嵌套对象导致旧值不可用的问题。

### D5: 删除不级联实体

删除树节点只移除 `nodes` 中的树节点，不删除链接的 inode 实体。

- **理由**：一个实体可能被多个树节点引用；树节点删除不应隐式删除实体。

### D6: 编辑中卡片警告描边

所有被锁定的节点卡片（无论持有者）使用 `--app-warning` 描边。

- **理由**：协作时明确提示哪些节点正在被编辑。

## Risks / Trade-offs

- [扁平表删除子树需多次 removeField] → 删除前先检查所有后代锁，从深层开始逐个删除，避免悬空引用。
- [路径段回退依赖同级名称唯一] → 服务端已强制同级节点名称唯一，路径可作为稳定回退依据。
- [文件节点不能有 children 由服务端校验] → 前端添加/编辑也会限制，避免导出时产生非法树。

## Migration Plan

1. `types.ts` 更新 `FileTreeState`/`FileTreeNode`，`file-node` ui_kind 改为 `form`。
2. 服务端 `validateStateShape` 更新 file-tree 校验。
3. 前端 `createTemplates.json` 更新默认值。
4. 删除 `FileTreeNodeEditor.vue`，清理 registry。
5. 实现专用 FileTreeEditor 及子组件。
6. 更新测试与文档。

## Open Questions

无。
