# Editor-Workspace Specification

## Purpose

Provides the browser-based multi-user editor workspace for browsing and editing puzzle module entities, connecting the frontend UI to the backend HTTP/WS APIs with tabs, locking, presence, and a resizable three-pane layout.

## Requirements

### Requirement: Editor workspace layout

The system SHALL provide a `/projects/:id` editor route protected by authentication. The editor page SHALL render a left-center-right three-pane layout with an initial width ratio of approximately `2:3:2`. The user SHALL be able to drag the separators between panes to adjust widths, subject to minimum pane widths.

#### Scenario: Open editor page

- **WHEN** an authenticated user navigates to `/projects/:id` for an existing project
- **THEN** the page renders three panes: entity browser, editor workspace, and tool panel, with draggable separators between them.

#### Scenario: Resize panes by dragging

- **WHEN** the user drags the left or right separator
- **THEN** the adjacent pane widths change continuously and the layout remains usable without page reload.

### Requirement: Entity browser

The system SHALL display all entities of the current project as a scrolling flow of cards. Each card SHALL show the entity `resource_id` and a visual indicator of which users are currently focused on that entity. The browser SHALL support filtering by `kind` and by `group`. Clicking a card SHALL open the entity in the editor workspace.

#### Scenario: Cards show resource_id and presence

- **WHEN** a user opens a project containing entities and other users are focused on an entity
- **THEN** each entity card displays its `resource_id`, and the card for the focused entity shows the focused users.

#### Scenario: Filter by kind and group

- **WHEN** a user selects a `kind` and/or `group` filter
- **THEN** the entity browser shows only entities matching all selected filters.

#### Scenario: Open entity from card

- **WHEN** a user clicks an entity card
- **THEN** an editor for that entity opens in the middle workspace, or the existing tab for that entity is activated if already open.

### Requirement: Multi-tab editor workspace

The editor workspace SHALL support multiple open entities as tabs ordered in a tab bar. Switching tabs SHALL preserve each editor’s component state without rebuilding it. A tab SHALL be closable manually. Below the tab bar SHALL be an operation bar providing generic entity operations, including version rollback, for the active entity.

#### Scenario: Open two entities as tabs

- **WHEN** a user opens two entity cards
- **THEN** the workspace shows two tabs and the most recently opened entity is active.

#### Scenario: Switch tabs preserves state

- **WHEN** a user edits a field in tab A, switches to tab B, then switches back to tab A
- **THEN** tab A shows the same component state including unsaved draft content without being recreated.

#### Scenario: Close active tab

- **WHEN** a user closes the active tab
- **THEN** the tab is removed and another open tab becomes active, or the workspace shows an empty state when no tabs remain.

#### Scenario: Rollback from operation bar

- **WHEN** a user triggers rollback for the active entity from the operation bar
- **THEN** the frontend sends a rollback request and updates the entity store from the room broadcast.

### Requirement: Editor component selection

The system SHALL select the editor component for an opened entity based on the entity’s `kind`, with a fallback to its `ui_kind` and a generic form editor for unknown types. The editor component mapping SHALL be extensible through a central registration mechanism.

#### Scenario: Known kind maps to specialized editor

- **WHEN** a user opens a `code` entity
- **THEN** the workspace renders the registered code editor for that kind.

#### Scenario: Unknown kind falls back

- **WHEN** a user opens an entity whose kind/ui_kind has no explicit editor registration
- **THEN** the workspace renders a generic form/read-only editor without breaking the tab.

### Requirement: Right tool panel

The system SHALL provide a right tool panel with a vertical icon rail for switching between tool panels. The first tool panel SHALL be a file manager that lists backend resource files, supports uploading a new file, downloading an existing file, and deleting a file.

#### Scenario: Switch to file manager panel

- **WHEN** a user clicks the file manager icon in the tool rail
- **THEN** the file manager panel becomes visible and lists resource files from the backend.

#### Scenario: Upload file

- **WHEN** a user selects a file in the file manager and confirms upload
- **THEN** the file is uploaded to the backend and appears in the file list after the response completes.

#### Scenario: Delete file

- **WHEN** a user deletes a file in the file manager
- **THEN** the file is removed from the backend and disappears from the file list.

### Requirement: Entity store and persistence

The system SHALL keep a single-layer entity store keyed by entity UUID for the current project. All WS sync events (`sync`, `created`, `update`, `rolled_back`, `deleted`) SHALL update this store. The store SHALL be persisted to `localStorage` together with layout widths. On project open, persisted data MAY be used as the initial sync vector, but the server `sync` response SHALL be treated as authoritative.

#### Scenario: Updates reflect in entity store

- **WHEN** a WS `update` message is received for an entity
- **THEN** the entity store replaces the stored entity state/version/revision and all UI views read from the store reflect the change.

#### Scenario: Deleted entity removed from store

- **WHEN** a WS `deleted` message is received
- **THEN** the entity is removed from the store and the localStorage cache is updated.

#### Scenario: Server sync is authoritative

- **WHEN** the client joins a project with stale local entity data
- **THEN** the client applies the `sync` response and overwrites local cache entries according to the server’s entities and `removed_ids`.

### Requirement: Communication client

The system SHALL provide a dedicated communication client that wraps HTTP and WebSocket messaging. The WebSocket client SHALL expose active functions for sending sync messages and a message-subscription mechanism for receiving server broadcasts. Subscriptions SHALL be removable to prevent leaks.

#### Scenario: Active send function

- **WHEN** a component calls the client’s patch function with an entity id, data path, and value
- **THEN** the client sends a `patch` message over the WebSocket.

#### Scenario: Subscribe to server broadcast

- **WHEN** a store subscribes to `update` messages through the client
- **THEN** the callback runs for every received `update` message and unsubscribing prevents further callbacks.

### Requirement: Lock visual feedback

The system SHALL display lock state on editable fields. When a field is locked by another user, the field SHALL appear visually locked and SHALL show the locking user’s identity.

#### Scenario: Locked field is visually disabled

- **WHEN** another user holds a lock on a field and the current user views that field
- **THEN** the field is rendered in a locked style with the holder’s username visible and editing controls are disabled.

#### Scenario: Lock released enables editing

- **WHEN** the other user releases the lock
- **THEN** the field returns to editable state and the lock indicator disappears.

### Requirement: Presence display

The system SHALL display user presence at entity level and field level. Entity-level presence SHALL appear in entity browser cards. Field-level presence SHALL appear on the relevant field when a user is focused there. Opening, switching, or closing entity editors SHALL update the current user’s entity-level focus.

#### Scenario: Entity-level presence on card

- **WHEN** another user focuses on an entity without a specific field
- **THEN** the entity card shows that user as present on the entity.

#### Scenario: Field-level presence

- **WHEN** another user focuses on a specific data path of an entity
- **THEN** the corresponding field in the editor shows that user’s presence indicator.

#### Scenario: Switching editor updates focus

- **WHEN** the current user switches to another open editor tab
- **THEN** the client sends the updated entity-level focus for the newly active entity.

### Requirement: Code editing

The system SHALL provide a Python code editing experience for code-capable editors (`code` and script editors). Code editors SHALL use CodeMirror 6 with Python language support and SHALL submit edited content through the existing WS patch flow.

#### Scenario: Edit Python block content

- **WHEN** a user edits the content of a `code` and triggers save
- **THEN** the frontend locks the appropriate data path, sends a patch with the full content, and updates the entity store on success.

#### Scenario: Lock prevents concurrent code edit

- **WHEN** another user holds the lock for a code content path
- **THEN** the code editor is read-only and shows the lock holder.

### Requirement: ActionBar 两行布局

编辑器 ActionBar SHALL 分为两行。第一行横向 flex 包含 resource_id（可点击）、kind、`v{version} · r{revision}`、版本回退按钮和删除按钮。第二行为注释 surface，完整展示注释并提供"编辑"/"添加"按钮。

#### Scenario: 打开实体显示两行

- **WHEN** 用户打开任意实体
- **THEN** ActionBar 显示两行，第一行实体元数据与操作按钮，第二行注释区

### Requirement: resource_id 编辑

resource_id SHALL 以可点击按钮形式展示，点击后弹出模态对话框，仅允许修改 `:` 之后的 id 部分，命名空间前缀不可更改。编辑前 SHALL 获取 `@resource_id:` 锁。

#### Scenario: 修改 id 部分

- **WHEN** 用户点击 resource_id、修改 id 部分并保存
- **THEN** resource_id 更新，标签页标题同步更新

#### Scenario: 他人锁定时禁止编辑

- **WHEN** 他人持有 `@resource_id:` 锁
- **THEN** 当前用户按钮禁用并显示覆盖层

### Requirement: 标签页标题同步

标签页标题 SHALL 始终反映实体当前 `resource_id`，修改后自动更新。

#### Scenario: 修改后标题同步

- **WHEN** 实体 resource_id 由 `hint:a` 改为 `hint:b` 且标签已打开
- **THEN** 标签标题变为 `hint:b`

### Requirement: 注释展示与编辑

ActionBar 第二行 SHALL 展示完整多行注释。无注释时 surface 使用虚线边框和半透明配色。点击"编辑"/"添加"弹出模态对话框，编辑需获取 `@comment:` 锁。

#### Scenario: 有注释展示

- **WHEN** 实体有注释
- **THEN** ActionBar 完整展示多行注释，无高度限制

#### Scenario: 无注释样式

- **WHEN** 实体注释为空
- **THEN** 注释 surface 使用虚线边框、半透明配色，显示"无注释"

### Requirement: LockOverlay 组件复用

系统 SHALL 提供 `LockOverlay` 独立组件，供 resource_id 按钮和注释 surface 在他人锁定时展示覆盖层。

#### Scenario: resource_id 被锁定显示覆盖层

- **WHEN** 他人持有 `@resource_id:` 锁
- **THEN** resource_id 按钮上显示 LockOverlay，展示持有者用户名

#### Scenario: 注释被锁定显示覆盖层

- **WHEN** 他人持有 `@comment:` 锁
- **THEN** 注释 surface 上显示 LockOverlay

### Requirement: 删除实体 UI 提示

收到 `deleted` 消息后，系统 SHALL 记录被删除实体 id；对已打开该实体的标签，编辑器区域 SHALL 显示"实体已被删除"覆盖层并提供关闭按钮。

#### Scenario: 被删除实体显示提示

- **WHEN** 他人删除当前打开的实体
- **THEN** 编辑器区域显示删除覆盖层

#### Scenario: 关闭已删除标签

- **WHEN** 用户点击删除覆盖层的关闭按钮
- **THEN** 标签关闭，回到空状态

### Requirement: 回退错误模态框

版本回退失败（包括 `HISTORY_EMPTY`）SHALL 通过模态对话框展示错误信息，不在 ActionBar 内联插入文本提示。

#### Scenario: 回退到头显示模态框

- **WHEN** 实体无历史快照时用户点击版本回退
- **THEN** 弹出模态对话框显示错误信息

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

### Requirement: 编辑中节点提示

所有正在被编辑的 file-tree 节点卡片 SHALL 显示 `block: false` 的 `LockOverlay`，展示锁定者用户名，不区分锁持有者。系统 SHALL NOT 再使用 `--app-warning` 描边或降低亮度 filter 标记这些卡片；该覆盖层 SHALL 不阻挡鼠标事件、不改变光标。

#### Scenario: 他人编辑节点时显示非阻塞覆盖层

- **WHEN** 其他用户持有某个树节点路径的锁
- **THEN** 该节点卡片显示 `LockOverlay` 用户名标签，且不阻挡点击、不降低亮度

#### Scenario: 自己编辑节点时同样显示覆盖层

- **WHEN** 当前用户持有某个树节点路径的锁
- **THEN** 该节点卡片同样显示 `LockOverlay` 用户名标签，且不阻挡点击

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
