## Context

当前 `progress-dag` 只是 FormEditor 封装，且状态直接用 `progress-node` 的 stable_id 表达拓扑，节点与实体耦合。file-tree 已建立“容器内部节点 + 实体链接 + 专用编辑器 + 上下布局 + 锁/覆盖层”的成熟模式。同步协议为 WS v2，字段锁为每连接一把锁，patch 成功后自动释放。前端使用 Vue 3 + M3 token。

## Goals / Non-Goals

**Goals:**

- 将 `progress-dag` 重命名为 `dag`，采用扁平 `DagState` 模型。
- 提供与 file-tree 风格一致的专用 DAG 编辑器：上部可视化 + 下部信息面板。
- 使用 dagre 横向布局，孤立节点单独成行。
- 提供添加/编辑/删除节点、后继多选、锁定覆盖层。
- 将 `LockOverlay` 扩展为可阻塞/非阻塞两种模式，并复用到 file-tree 卡片。

**Non-Goals:**

- 不实现完整的拖拽连线式图编辑器。
- 不做旧 `progress-dag` 数据的自动迁移/向后兼容。
- 不引入 Canvas 渲染。
- 不实现 DAG 入口的专门可视化编辑 UI（入口通过 `entryIds` 数据维护，后续可扩展）。

## Decisions

### 1. 使用 dagre + HTML/SVG 自绘，而不是 nice-dag / vue-flow

- 选择 dagre：只负责布局，节点/边/交互全部自控，便于贴合 M3 和 file-tree 风格。
- nice-dag 提供 zoom/minimap/DnD 等完整能力，但内部 DOM 复杂、定制成本高。
- vue-flow 对当前“布局 + 点击详情 + 轻量编辑”需求过重。
- 渲染采用 HTML 节点卡片 + SVG 边；平移/缩放通过外层 `transform: translate(...) scale(...)` 实现。

### 2. 扁平 `DagState` 与 `successors: string[]`

- `DagState = { entryIds: string[], nodes: Record<string, DagNode> }`。
- `DagNode = { id, name, pnode, successors: string[] }`。
- 后继用 ID 列表而非内嵌对象，避免 DAG 中同一节点被多个前驱引用时重复存储。
- `pnode` 存 `progress-node` 实体 UUID，创建时前端必填；服务端仍允许 `null` 以兼容手工/历史数据。

### 3. 孤立节点不交给 dagre

- 先根据 `successors` 计算入边/出边集合，无任何边的节点标记为孤立。
- 连通节点统一交给 dagre 做 `LR` 布局；孤立节点单独排在主 DAG 行下方，手工计算行内坐标。
- 避免 dagre 把孤立节点与主图混在同一层，视觉更清晰。

### 4. 锁处理沿用 file-tree 模式

- 编辑节点：先 lock 节点路径再打开弹窗；保存成功由服务端自动释放；取消时手动 unlock。
- 删除节点：由于每连接只有一把锁，不能同时锁多条路径；改为逐路径 `lock → patch/remove`，并在操作前本地检查相关路径是否被他人锁定。
- DAG 卡片：被其他用户锁定时显示 `LockOverlay`（block 模式）；自己编辑不覆盖自身。
- file-tree 卡片：所有持锁卡片显示 `LockOverlay` 的 `block: false` 模式，仅作标签提示，不拦截点击。

### 5. `MultiSelectInput` 下拉不参与布局

- 已选卡片放在触发按钮上方，下拉菜单使用绝对定位悬浮层。
- 避免展开下拉时挤压弹窗布局，也避免已选卡片被下拉遮挡。

### 6. `LockOverlay` 增加 `block` 属性

- `block: true` 保持原行为：`backdrop-filter`、`pointer-events: auto`、`cursor: not-allowed`。
- `block: false` 仅显示用户名标签：`pointer-events: none`、无 backdrop、光标不变。
- 默认 `true`，现有调用无需改动。

## Risks / Trade-offs

- [Breaking rename `progress-dag` → `dag`] → 不提供自动迁移；旧容器数据需用户删除重建，文档/OpenSpec 同步标注 BREAKING。
- [每连接一把锁限制] → 删除/批量更新采用顺序 lock-patch，避免尝试同时持有多把锁。
- [dagre 对多个连通分量的布局不是组件感知] → 当前 puzzle DAG 规模小，可接受；后续如需要可自行按连通分量分组加偏移。
- [`pnode` 创建必填但服务端允许 null] → 前端保证新建节点必选；服务端保留 null 兼容旧数据/手工编辑。

## Migration Plan

1. 合并本 change 后，旧 `progress-dag` 实体不再被前端识别为 `dag`。
2. 用户需手动删除旧 `progress-dag` 容器并创建新的 `dag:main` 容器，再重新添加节点/后继。
3. 服务端测试与前端模板同步更新，无自动数据迁移。

## Open Questions

- 是否需要在 DAG 编辑器中提供专门的入口（`entryIds`）编辑 UI？当前可通过数据/后续扩展实现，不影响本 change 的既有规格。
