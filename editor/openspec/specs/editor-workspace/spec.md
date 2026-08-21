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

- **WHEN** a user opens a `python-block` entity
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

The system SHALL provide a Python code editing experience for code-capable editors (`python-block` and script editors). Code editors SHALL use CodeMirror 6 with Python language support and SHALL submit edited content through the existing WS patch flow.

#### Scenario: Edit Python block content

- **WHEN** a user edits the content of a `python-block` and triggers save
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
