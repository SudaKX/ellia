## Purpose

为 `dag` 容器提供专用可视化编辑器，使进度 DAG 的节点、后继关系和入口可以直观查看和编辑。

## ADDED Requirements

### Requirement: DAG 编辑器上下布局

系统 SHALL 为 `dag` kind 提供专用编辑器，采用上部 DAG 画布 + 下部信息面板布局。上部 SHALL 使用 dagre 横向布局渲染连通节点与边；孤立节点（无任何入边/出边）SHALL 单独排在主 DAG 行下方。用户 SHALL 能通过鼠标中键拖拽平移画布、通过滚轮缩放画布，并可通过工具栏按钮缩放/适应视图。

#### Scenario: 打开 dag 实体显示横向 DAG

- **WHEN** 用户打开 `dag` 实体且 state 中存在带后继关系的节点
- **THEN** 上部画布按从左到右方向显示节点和边，下部显示“选择节点查看详情”占位

#### Scenario: 孤立节点独立成行

- **WHEN** DAG 中存在没有任何入边/出边的节点
- **THEN** 该节点显示在主 DAG 行下方，不参与 dagre 主布局

#### Scenario: 中键拖拽平移

- **WHEN** 用户在画布上按下鼠标中键并拖拽
- **THEN** 画布视图跟随拖拽平移，且浏览器默认中键自动滚动被阻止

### Requirement: DAG 节点卡片

DAG 节点卡片 SHALL 展示两行信息：首行为节点 `name`，次行为关联 `progress-node` 实体的 `resource_id`（未关联时显示“未关联”）。节点卡片 SHALL 仅响应鼠标左键点击进行选中。被其他用户锁定的节点卡片 SHALL 显示 `LockOverlay`，不再使用 warning 描边。

#### Scenario: 卡片展示名称与资源 ID

- **WHEN** 用户查看一个已关联 `pnode` 的 DAG 节点卡片
- **THEN** 卡片首行显示 `name`，次行显示对应 `progress-node` 的 `resource_id`

#### Scenario: 仅左键选中节点

- **WHEN** 用户使用鼠标中键或右键点击节点卡片
- **THEN** 不触发节点选中

#### Scenario: 其他用户锁定时显示覆盖层

- **WHEN** 其他用户持有某 DAG 节点路径的锁
- **THEN** 该节点卡片显示 `LockOverlay`，展示锁定者用户名

### Requirement: 添加与编辑 DAG 节点

添加 DAG 节点 SHALL 通过模态对话框完成。节点 `name` SHALL 必填；`pnode` SHALL 必填并通过带搜索的下拉选择已有 `progress-node` 实体；后继节点 SHALL 通过可复用多选组件选择其他 DAG 节点。编辑节点 SHALL 允许修改 `name`、`pnode` 和 `successors`，并遵循字段锁。

#### Scenario: 添加节点必须填写名称和 pnode

- **WHEN** 用户添加 DAG 节点但未填写 `name` 或未选择 `pnode`
- **THEN** 保存被阻止并显示错误提示

#### Scenario: 后继多选

- **WHEN** 用户添加/编辑节点时从多选组件选择后继节点
- **THEN** 已选后继以流式卡片展示，可点击 `×` 移除

#### Scenario: 编辑节点使用字段锁

- **WHEN** 用户编辑一个未被其他用户锁定的 DAG 节点
- **THEN** 编辑器先获取该节点路径锁，保存成功后自动释放，取消时释放

### Requirement: 删除 DAG 节点

删除 DAG 节点 SHALL 同时清理其他节点 `successors` 中对它的引用，以及 `entryIds` 中的入口引用。删除前 SHALL 检查相关路径是否被他人锁定；被锁定则阻止删除。

#### Scenario: 删除节点清理引用

- **WHEN** 用户删除一个被其他节点作为后继、且被列为入口的 DAG 节点
- **THEN** 该节点被移除，其他节点 `successors` 和 `entryIds` 中不再包含它

#### Scenario: 相关路径被锁定时阻止删除

- **WHEN** 待删除节点自身或其相关引用路径被其他用户锁定
- **THEN** 删除被阻止并显示错误提示

### Requirement: 下部信息面板

`dag` 编辑器下部 SHALL 展示选中节点关联 `progress-node` 实体的 `resource_id` 与 `comment`，并提供“打开”按钮跳转到该实体编辑器。节点未关联实体时 SHALL 显示缺失提示。

#### Scenario: 打开关联实体

- **WHEN** 用户点击已关联节点的“打开”按钮
- **THEN** 打开对应 `progress-node` 实体的编辑标签
