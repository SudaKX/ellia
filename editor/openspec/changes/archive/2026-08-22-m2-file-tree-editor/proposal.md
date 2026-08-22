## Why

file-tree 是文件树拓扑容器，之前只复用 FormEditor/JSON 编辑，无法直观编辑父子层级、文件夹/文件类型和 inode 引用。需要专门的拓扑编辑器，并让 file-node 回归通用 FormEditor。

## What Changes

- **FileTreeState 扁平化**：改为 `{rootId, nodes}`，`FileTreeNode` 包含 `id/name/isDirectory/inode/parent/order`；树内节点 ID 与 inode 实体 ID 分离
- **显式文件夹/文件**：`isDirectory=true` 时 `inode` 必须为 `null` 且可有 children；`isDirectory=false` 时必须指定 `inode` 且不能有 children
- **添加节点只引用现有实体**：添加节点时通过 `inode` 下拉选择已有 `file-node`/`artifact-node`，不再在 file-tree 内创建实体或记录 artifact/node_generator
- **FileTreeNodeEditor 移除**：删除 `FileTreeNodeEditor.vue`，`file-node` 默认 `ui_kind` 改为 `form`
- **专用 FileTreeEditor**：横向多层级、节点卡片、添加/编辑/删除弹窗、下部信息面板、复制路径、打开链接实体
- **协作与回退**：删除节点不删除 inode 实体；被删除节点按记录路径回退到第一个仍存在的路径；右上角 toast 提示；正在编辑的节点卡片使用 `--app-warning` 描边
- **服务端校验增强**：同级节点名称唯一、非根节点必须指定 parent、文件节点不能包含 children

## Capabilities

### New Capabilities
- `file-tree-editor`: 专用 file-tree 拓扑编辑器（层级、卡片、添加/编辑/删除、toast、路径回退、编辑中描边）

### Modified Capabilities
- `entity-sync`: `FileTreeState` 改为扁平节点表；`FileTreeNode` 增加 `isDirectory`；服务端校验文件夹/文件约束与同级重名
- `editor-workspace`: 注册 `file-tree` 专用编辑器；`file-node` 使用 FormEditor；`tree-node` ui_kind 移除

## Impact

- **共享包**：`types.ts` 修改 `FileTreeState`/`FileTreeNode`，`UI_KINDS` 移除 `tree-node`，`file-node` ui_kind 改为 `form`
- **服务端**：`entities.ts` `validateStateShape` 增加 file-tree 扁平节点校验、isDirectory 约束、同级重名校验、文件节点无 children 校验
- **前端**：删除 `FileTreeNodeEditor.vue`；重写 `FileTreeEditor.vue`；新增 `file-tree/` 子组件（FileTreeView、FileTreeLevel、TreeNodeCard、NodeInfoPanel、AddNodeDialog、useFileTree）；`registry.ts` 更新；`createTemplates.json` 更新默认值
- **测试**：`entities.test.ts`、`sync.test.ts` 更新 file-tree state 与 file-node ui_kind
