## 1. 共享类型与服务端

- [x] 1.1 `types.ts`：`FileTreeState` 改为 `{rootId, nodes}`；`FileTreeNode` 增加 `id/name/isDirectory/inode/parent/order`
- [x] 1.2 `types.ts`：`UI_KINDS` 移除 `tree-node`；`file-node` 默认 ui_kind 改为 `form`
- [x] 1.3 `entities.ts`：`validateStateShape` 校验扁平节点表、根节点、`isDirectory` 约束、同级名称唯一、非根节点 parent 必填、文件节点无 children
- [x] 1.4 `createTemplates.json`：`file-tree` 默认值更新为 `{rootId, nodes:{root}}` 且 root 含 `isDirectory:true`

## 2. 前端编辑器

- [x] 2.1 删除 `FileTreeNodeEditor.vue`；清理 `registry.ts` 中 `file-node`/`tree-node` 注册
- [x] 2.2 重写 `FileTreeEditor.vue`：横向层级、添加/编辑/删除、toast、路径回退、删除不级联实体
- [x] 2.3 新增 `file-tree/FileTreeView.vue`：多层级横向容器、父链高亮、单段路径标题
- [x] 2.4 新增 `file-tree/FileTreeLevel.vue`：单层节点列表、添加按钮、编辑中描边透传
- [x] 2.5 新增 `file-tree/TreeNodeCard.vue`：紧凑卡片、hover 填充、selected/highlighted/editing 状态
- [x] 2.6 新增 `file-tree/NodeInfoPanel.vue`：左右两栏、编辑弹窗、复制路径、打开实体、LockOverlay 复用
- [x] 2.7 新增 `file-tree/AddNodeDialog.vue`：文件夹/文件切换、name + inode 引用选择
- [x] 2.8 新增 `file-tree/useFileTree.ts`：children 推导、路径生成、后代枚举、order 计算

## 3. 协作与交互

- [x] 3.1 删除树节点不删除 inode 实体
- [x] 3.2 外部/协同删除按记录路径段回退到第一个仍存在的路径
- [x] 3.3 编辑器右上角 toast 提示
- [x] 3.4 正在被编辑的节点卡片（所有持有者）使用 `--app-warning` 描边
- [x] 3.5 `EntityReferenceSelect` 增加 `placeholder` 支持

## 4. 测试与验证

- [x] 4.1 更新 `entities.test.ts`：file-tree 新 state、file-node ui_kind form
- [x] 4.2 更新 `sync.test.ts`：file-tree 新 state 与 nodes patch
- [x] 4.3 运行 `pnpm type-check` 通过
- [x] 4.4 运行 `pnpm --dir apps/server test`（73 个用例全绿）
- [x] 4.5 运行 `pnpm build` 通过
