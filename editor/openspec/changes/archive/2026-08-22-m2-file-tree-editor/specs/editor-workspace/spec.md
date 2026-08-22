## ADDED Requirements

### Requirement: file-tree 专用拓扑编辑器

系统 SHALL 为 `file-tree` kind 提供专用编辑器，不再复用 FormEditor/JSON fallback。编辑器 SHALL 以上部横向多层级 + 下部信息面板布局呈现。

#### Scenario: 打开 file-tree 实体显示层级树

- **WHEN** 用户打开 `file-tree` 实体
- **THEN** 编辑器上部显示多个横向层级，每个层级展示该父节点下的节点卡片，并可从文件夹节点向右展开下一层

#### Scenario: 文件节点不展开下一层

- **WHEN** 用户选中 `isDirectory:false` 的文件节点
- **THEN** 编辑器不展开该文件节点的子层级，只停留在其父层级

### Requirement: 添加节点

添加节点 SHALL 通过模态对话框完成。用户 SHALL 选择“文件夹”或“文件”；文件夹 SHALL 不要求 `inode`，文件 SHALL 通过 `inode` 命名空间下拉选择已有 `file-node`/`artifact-node` 实体并记录实体 ID。添加前 SHALL 检查同级名称唯一。

#### Scenario: 添加文件夹

- **WHEN** 用户在当前层级选择“文件夹”、输入名称并确认
- **THEN** 创建 `isDirectory:true`、`inode:null` 的树节点

#### Scenario: 添加文件

- **WHEN** 用户选择“文件”、输入名称并从 inode 下拉选择实体
- **THEN** 创建 `isDirectory:false`、`inode:<实体ID>` 的树节点

#### Scenario: 同级重名被阻止

- **WHEN** 用户添加的节点名称与同层级已有节点名称相同
- **THEN** 添加被阻止并显示提示

### Requirement: 节点编辑与删除

节点编辑 SHALL 通过模态对话框进行，仅允许修改 `name`（以及文件的 `inode`）。删除树节点 SHALL 仅移除树节点，不删除链接的 inode 实体；删除前 SHALL 检查所有后代树节点锁。

#### Scenario: 编辑节点

- **WHEN** 用户点击“编辑”并修改名称/inode 后保存
- **THEN** 对应 `FileTreeNode` 通过 `@state:/nodes/<id>` patch 更新

#### Scenario: 删除节点不删除实体

- **WHEN** 用户删除一个文件树节点
- **THEN** 该树节点及其后代树节点被移除，但链接的 `file-node`/`artifact-node` 实体保留

#### Scenario: 后代存在锁时删除被阻止

- **WHEN** 待删除节点的任意后代树节点路径被他人锁定
- **THEN** 删除被阻止并显示错误

### Requirement: 删除后路径回退

当当前选中节点或其父链节点被删除（包括协同删除）时，编辑器 SHALL 按记录路径段回退到第一个仍存在的路径，并在编辑器右上角显示 toast 提示。

#### Scenario: 删除选中节点回退到父层

- **WHEN** 用户删除当前选中的节点
- **THEN** 选中状态回退到该节点的父节点，并显示 toast

#### Scenario: 协同删除父链节点回退

- **WHEN** 其他用户删除了当前选中节点的父节点
- **THEN** 编辑器按记录路径段回退到第一个仍存在的祖先，并显示 toast

### Requirement: 编辑中节点警告描边

所有正在被编辑的 file-tree 节点卡片 SHALL 使用 `--app-warning` 颜色描边，不区分锁持有者。

#### Scenario: 他人编辑节点时显示警告描边

- **WHEN** 其他用户持有某个树节点路径的锁
- **THEN** 该节点卡片显示 `--app-warning` 描边

### Requirement: 下部信息面板

file-tree 编辑器下部 SHALL 为左右两栏：左侧展示节点摘要与链接 inode 实体的 `resource_id`/`comment`，右侧放置操作按钮（编辑、打开、复制路径、删除）。打开按钮 SHALL 跳转到 inode 链接实体；复制路径 SHALL 复制当前节点完整路径。

#### Scenario: 打开链接实体

- **WHEN** 用户点击“打开”
- **THEN** 打开 `inode` 引用的 `file-node`/`artifact-node` 实体编辑标签

#### Scenario: 复制路径

- **WHEN** 用户点击“复制路径”
- **THEN** 当前节点完整路径被复制到剪贴板，按钮短暂显示“已复制”

### Requirement: file-node 编辑器回退

系统 SHALL 移除 `FileTreeNodeEditor`；`file-node` 默认 `ui_kind` 为 `form`，使用通用 FormEditor 编辑。

#### Scenario: file-node 使用 FormEditor

- **WHEN** 用户打开 `file-node` 实体
- **THEN** 渲染通用 FormEditor
