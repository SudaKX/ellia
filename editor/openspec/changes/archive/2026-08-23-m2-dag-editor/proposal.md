## Why

当前 `progress-dag` 仍只是 FormEditor 封装，缺少可视化 DAG 编辑能力；同时其数据模型直接使用 `progress-node` 的 stable_id 表达拓扑，导致图内节点与实体耦合、难以支持孤立节点/多 DAG 的清晰编辑。需要将容器简化为 `dag`，并提供一个与 file-tree-editor 同风格的专用 DAG 编辑器。

## What Changes

- **BREAKING**: 将 `progress-dag` kind / namespace / ui_kind 重命名为 `dag`。
- **BREAKING**: 将 DAG 状态模型改为 `{ entryIds, nodes }`：
  - `DagNode` 包含 `id`（图内 UUID）、`name`（必填可读名）、`pnode`（关联 `progress-node` 实体 ID）、`successors`（后继 DAG 节点 ID 列表）。
  - 图内节点与 `progress-node` 实体解耦，通过 `pnode` 属性链接。
- 服务端新增 `dag` state 校验：`name` 非空、`successors`/`entryIds` 必须引用已存在的 DAG 节点、禁止自环和重复后继；`pnode` 外部实体允许悬空。
- 新增 `DagEditor` 专用编辑器：
  - 上部 DAG 画布：dagre 横向布局、孤立节点独立行、中键拖拽平移、滚轮缩放、右下角 M3 FAB 添加节点。
  - 下部信息面板：展示 `resource_id`/`comment`，提供“打开”跳转、编辑、删除。
  - 添加/编辑弹窗：必填 `name`、必填 `pnode`（带搜索下拉）、后继多选用可复用组件。
  - 被他人锁定的 DAG 节点卡片直接复用 `LockOverlay`（block 模式），不再使用 warning 描边。
- 新增可复用 `MultiSelectInput`：带搜索下拉 + 横向流式已选卡片 + 每项 `×` 移除。
- 调整 `LockOverlay`：新增 `block?: boolean` 属性，默认 `true`；`block: false` 时不降低亮度、不阻挡鼠标事件、不改变光标。
- 调整 file-tree 编辑器：卡片上的编辑中样式从 `--app-warning` 描边 + filter 改为 `block: false` 的 `LockOverlay`。
- 微调 file manager 卡片：hover 才填充背景，选中仅描边。

## Capabilities

### New Capabilities

- `dag-editor`: 专用 DAG 容器编辑器的可视化布局、节点/后继编辑、锁定展示与交互行为。

### Modified Capabilities

- `entity-sync`: `progress-dag` 重命名为 `dag`，DAG 状态模型与校验规则更新。
- `editor-workspace`: file-tree 节点卡片编辑中提示从 warning 描边改为非阻塞 LockOverlay；补充 dag 编辑器在编辑器工作区中的行为（若并入工作区 spec）。
- `entity-editor-lock-overlay`: `LockOverlay` 增加可选 `block` 属性，支持非阻塞展示模式。

## Impact

- `packages/puzzle-schema/src/types.ts`：`DagNode`/`DagState`、kind/namespace/ui_kind 映射。
- `apps/server/src/services/entities.ts`：`dag` state 校验。
- `apps/server/tests/*`：dag 创建/容器 patch 测试。
- `apps/web/src/components/editor/panes/DagEditor.vue` 及 `panes/dag/*`：新 DAG 编辑器。
- `apps/web/src/components/ui/MultiSelectInput.vue`：新多选组件。
- `apps/web/src/components/presence/LockOverlay.vue`：`block` 属性与标签样式。
- `apps/web/src/components/editor/panes/file-tree/*`：卡片 LockOverlay 替换。
- `apps/web/src/components/tools/panels/FileManagerPanel.vue`：卡片 hover/selected 样式。
- 依赖：`@dagrejs/dagre` 新增到 `apps/web`。
