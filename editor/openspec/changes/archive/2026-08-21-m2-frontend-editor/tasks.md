## 1. 共享协议与后端扩展

- [x] 1.1 更新 `packages/puzzle-schema/src/sync.ts`：`FocusMessage.entity_id` 允许 `EntityId | null`；`UnlockMessage` 增加可选 `ref`；`LockedMessage`、`UnlockedMessage`、`DeletedMessage`、`RolledBackMessage` 增加可选 `ref`
- [x] 1.2 更新 `packages/puzzle-schema/src/sync.ts` 或 `types.ts`：增加文件列表响应类型 `FileListResponse { files: FileRecord[] }`（如必要）
- [x] 1.3 更新 `apps/server/src/ws/hub.ts`：`unlock` 处理器读取并回传 `ref`；`lock` 成功广播 `locked` 携带 `ref`；`delete` 广播 `deleted` 携带 `ref`；`rollback` 广播 `rolled_back` 携带 `ref`
- [x] 1.4 更新 `apps/server/src/ws/hub.ts`：`focus` 处理器允许 `entity_id: null`，null 时清除该连接 focus 并广播 presence
- [x] 1.5 更新 `apps/server/src/services/files.ts`：新增 `listFiles()` 按 `created_at DESC` 查询全部文件
- [x] 1.6 更新 `apps/server/src/routes/files.ts`：挂载 `GET /api/files`，返回 `{ files: [...] }`，沿用 `requireAuth`
- [x] 1.7 更新后端测试：覆盖文件列表、`ref` 回传、clear focus；运行 `pnpm --dir apps/server test` 保持全绿

## 2. 前端通讯层

- [x] 2.1 在 `apps/web/src/client/` 建立目录结构：`http.ts`、`rest/`、`ws/`；将现有 `api/` 的 fetch 封装迁移/复用到 `client/http.ts`
- [x] 2.2 实现 `client/rest/projects.ts`：`listProjects`、`createProject`、`getProject`、`updateProject`
- [x] 2.3 实现 `client/rest/files.ts`：`listFiles`、`uploadFile`、`downloadFile`、`deleteFile`
- [x] 2.4 实现 `client/ws/SyncClient.ts`：WebSocket 生命周期、`send`、类型化 `on/off` 订阅、心跳 `ping`
- [x] 2.5 在 `SyncClient` 实现 Promise 式主动函数：`create`、`patch`、`lock`、`unlock`、`delete`、`rollback`、`history`，通过 `ref` 匹配 ack/broadcast 与 `error`
- [x] 2.6 在 `SyncClient` 实现 `join(projectId, vector)`、`focus(entityId | null, dataPath?)`、`ping()` 等主动接口

## 3. 前端 Stores

- [x] 3.1 新增 `stores/projects.ts`：项目列表、当前项目、加载/创建项目
- [x] 3.2 新增 `stores/entities.ts`：单层 `Record<EntityId, EntityRecord>`，订阅 `sync/created/update/rolled_back/deleted`，支持按当前项目加载/清空
- [x] 3.3 在 `stores/entities.ts` 实现 localStorage 持久化：`ellia:entities:<projectId>` 读写、debounce、解析失败降级
- [x] 3.4 新增 `stores/editorTabs.ts`：打开/激活/关闭标签，`activeEntityId`，`tabComponentNames`
- [x] 3.5 新增 `stores/locks.ts`：`locked/unlocked/lock_denied` 更新锁表，暴露 `isLocked`、`holderOf`
- [x] 3.6 新增 `stores/presence.ts`：保存 `PresenceUser[]`，暴露 `usersByEntity`、`userAtPath`
- [x] 3.7 新增 `stores/toolPanel.ts`：右侧工具面板 selected tool 状态
- [x] 3.8 在 `stores/entities.ts` 或独立工具中实现布局宽度持久化：`ellia:layout:<projectId>`

## 4. 项目列表与路由

- [x] 4.1 改造 `views/HomeView.vue`：展示项目列表、新建项目表单（module_id/display_name）、错误提示
- [x] 4.2 新增 `views/ProjectView.vue`：读取项目、初始化 SyncClient、join 当前项目、加载 entity store
- [x] 4.3 在 `router/index.ts` 增加 `/projects/:id` 路由（`requiresAuth`），保留现有认证守卫
- [x] 4.4 在 `App.vue` 导航中补充项目入口/返回（如需要）

## 5. 编辑器布局与工作区

- [x] 5.1 实现 `components/split/`：`SplitDivider.vue`、`ResizableSplit.vue`，使用 pointer 拖拽和最小宽度
- [x] 5.2 新增 `layouts/EditorLayout.vue`：左中右三段，初始 `2:3:2`，读取/保存布局宽度
- [x] 5.3 实现 `components/editor/EditorPaneHost.vue`：标签栏 + 操作栏 + KeepAlive 编辑器容器
- [x] 5.4 实现 `components/editor/EditorTabBar.vue`：标签展示、激活、手动关闭
- [x] 5.5 实现 `components/editor/EditorActionBar.vue`：显示当前实体信息、版本回退按钮、删除按钮
- [x] 5.6 实现 `components/editor/registry.ts`：`registerKindEditor`、`registerUiKindEditor`、`resolveEditorForEntity`
- [x] 5.7 实现 `components/editor/panes/FormEditor.vue`：通用结构化表单/JSON 只读兜底编辑器
- [x] 5.8 在 `ProjectView.vue` 组合 `EditorLayout`：左实体浏览器、中 EditorPaneHost、右 ToolPanel

## 6. 左侧实体浏览器

- [x] 6.1 实现 `components/entity-browser/EntityBrowser.vue`：卡片流布局、空状态
- [x] 6.2 实现 `components/entity-browser/EntityCard.vue`：显示 `resource_id`、kind/group、在线用户角标、点击打开/激活标签
- [x] 6.3 实现 `components/entity-browser/EntityFilterBar.vue`：按 kind 和 group 筛选，选项来自当前实体 store
- [x] 6.4 接入 presence store：卡片显示关注该实体的用户

## 7. 锁与在场 UI

- [x] 7.1 实现通用 `components/presence/UserBadge.vue`：显示用户名/头像缩略
- [x] 7.2 实现通用 `components/presence/LockHint.vue`：锁定态提示条，显示持有者
- [x] 7.3 在 `FormEditor` 和各字段组件中接入 `locks` store：锁定字段禁用/样式变化
- [x] 7.4 在编辑器字段容器中展示字段级 presence：聚焦用户头像出现在对应字段旁
- [x] 7.5 实现打开/切换/关闭标签时的 focus 更新；关闭最后一个标签发送 `focus(null)` 清除位置

## 8. 右侧工具面板与文件管理

- [x] 8.1 实现 `components/tools/ToolRail.vue`：图标栏、选中态、切换面板
- [x] 8.2 实现 `components/tools/panels/FileManagerPanel.vue`：文件列表、上传按钮、下载链接、删除确认
- [x] 8.3 接入 `client/rest/files.ts`：列表加载、上传后刷新、删除后刷新、错误提示
- [x] 8.4 在 `EditorLayout` 右侧接入 ToolRail + FileManagerPanel

## 9. 编辑器组件

- [x] 9.1 为 `apps/web` 添加 CodeMirror 6 依赖：`codemirror`、`@codemirror/lang-python`、`@codemirror/state`、`@codemirror/view`
- [x] 9.2 实现 `components/editor/panes/CodeEditor.vue`：CodeMirror Python 编辑、锁定态只读、500ms debounce patch
- [x] 9.3 实现 `components/editor/panes/ScriptEditor.vue`：脚本编辑器（可复用 CodeEditor 组件）
- [x] 9.4 实现 `components/editor/panes/AssetEditor.vue`：显示 asset 元数据、文件引用、上传/替换文件
- [x] 9.5 实现 `components/editor/panes/ProgressNodeEditor.vue`、`FileTreeNodeEditor.vue` 的基础表单
- [x] 9.6 实现 `components/editor/panes/FileTreeEditor.vue`、`ProgressDagEditor.vue` 的容器拓扑基础编辑
- [x] 9.7 在 `registry.ts` 注册所有已实现的 kind/ui_kind 编辑器

## 10. 集成验证与文档

- [x] 10.1 运行 `pnpm install --frozen-lockfile`、`pnpm type-check`、`pnpm build`
- [x] 10.2 运行 `pnpm --dir apps/server test` 确认后端扩展未破坏现有测试
- [x] 10.3 手工冒烟：登录 → 项目列表 → 新建项目 → 打开项目 → 多标签编辑 → 锁冲突/释放 → presence 展示 → 文件上传/下载/删除
- [x] 10.4 双浏览器验证：字段锁定、实时广播、focus 清除、断线清理
- [x] 10.5 更新 `docs/handoff.md` 与 `README.md`：M1.2b/M2 前端完成状态、新增 API/协议说明
- [x] 10.6 运行 `openspec validate m2-frontend-editor` 确认 change 有效