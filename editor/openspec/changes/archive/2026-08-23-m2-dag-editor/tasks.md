## 1. Schema 与后端

- [x] 1.1 在 `packages/puzzle-schema/src/types.ts` 中将 `progress-dag` kind/namespace/ui_kind 重命名为 `dag`
- [x] 1.2 更新 `DagNode`/`DagState`：`DagNode` 包含 `id/name/pnode/successors`，`DagState` 包含 `entryIds/nodes`
- [x] 1.3 更新 `apps/server/src/services/entities.ts` 的 `dag` state 校验：`name` 非空、`successors`/`entryIds` 内部引用必须存在、禁止自环/重复后继
- [x] 1.4 更新 `apps/server/tests/entities.test.ts` 与 `sync.test.ts` 中的 dag 创建/容器 patch 用例

## 2. DAG 编辑器核心

- [x] 2.1 在 `apps/web` 添加 `@dagrejs/dagre` 依赖
- [x] 2.2 实现 `panes/dag/useDag.ts`：从 `DagState` + progress-node 实体组装布局，dagre 横向 `LR` 布局，孤立节点独立行
- [x] 2.3 实现 `DagView.vue`：SVG 边 + HTML 节点卡片、中键拖拽平移、滚轮缩放、适应视图、右下角 FAB 添加按钮
- [x] 2.4 实现 `DagNodeCard.vue`：两行卡片（name / resource_id），仅左键选中，其他用户锁定时显示 `LockOverlay`
- [x] 2.5 实现 `DagNodeDialog.vue`：添加/编辑节点，必填 `name`、必填 `pnode`（带搜索下拉）、后继多选
- [x] 2.6 实现 `DagNodeInfoPanel.vue`：下部展示 `resource_id`/`comment`，提供打开/编辑/删除
- [x] 2.7 实现 `DagEditor.vue`：上下布局，处理添加/编辑/删除、字段锁、删除引用清理、本地状态更新
- [x] 2.8 更新 `registry.ts` 将 `dag` kind/ui_kind 注册到 `DagEditor`

## 3. 可复用组件与样式

- [x] 3.1 实现 `components/ui/MultiSelectInput.vue`：带搜索下拉、已选卡片在触发按钮上方、下拉绝对定位不参与布局、每项 `×` 移除
- [x] 3.2 为 `LockOverlay.vue` 增加 `block` 属性（默认 `true`），支持 `block: false` 非阻塞模式，并调整标签圆角/偏移
- [x] 3.3 更新 file-tree 卡片：移除 `--app-warning` 描边和 filter，改为 `block: false` 的 `LockOverlay`
- [x] 3.4 更新 `FileManagerPanel.vue` 卡片：默认透明、hover 填充、选中仅描边

## 4. 文档与验证

- [x] 4.1 更新 `docs/entity-editor-todo.md` 和 `docs/handoff.md` 中的 `dag` 命名与编辑器状态
- [x] 4.2 同步 OpenSpec 主 specs：`entity-sync`、`editor-workspace`、`entity-editor-lock-overlay`，并归档本 change
- [x] 4.3 运行 `pnpm type-check`、`pnpm --dir apps/web build`、`pnpm --dir apps/server test`、`openspec validate --specs`
