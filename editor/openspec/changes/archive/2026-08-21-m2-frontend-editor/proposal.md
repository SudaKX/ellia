## Why

M2 后端同步与文件系统已经完成并通过 59 个测试，但前端仍停留在认证/管理界面：没有项目列表，也没有编辑器主界面。现在需要落地 M1.2b/M2 前端，把后端已经提供的 projects CRUD、WS v2 同步、字段锁、在场与文件能力变成可用的多人编辑体验。

## What Changes

- 新增前端项目列表页：展示/新建项目，点击进入 `/projects/:id` 编辑器页面。
- 新增经典左中右三段编辑器布局，初始比例约 `2:3:2`，支持拖动边界调整宽度。
- 左侧实体浏览器：流式实体卡片，卡片显示 `resource_id`、当前编辑该实体的用户；支持按 `kind` 与 `group` 筛选。
- 中部工作区：多标签页编辑器，标签切换时使用 `KeepAlive` 保留组件状态；标签栏下提供实体通用操作栏（含版本回退）；编辑器按实体的 `kind`/`ui_kind` 切换。
- 右侧工具面板：VSCode 风格图标栏；首个面板为文件管理，展示后端全部资源文件，支持上传、下载、删除。
- 抽离前端通讯层：`client` 统一负责 HTTP 与 WS；WS 暴露主动函数接口并使用消息-订阅机制分发广播。
- 引入单层 `<UUID, EntityRecord>` 实体 store，所有同步消息统一更新该 store，并持久化到 localStorage；同时持久化布局宽度。
- 实现锁与在场 UI：被锁字段有视觉提示并显示编辑者；卡片显示实体层在线用户；支持实体层/字段层两种位置展示。
- **后端文件列表 API**：新增 `GET /api/files` 返回全部文件元数据。
- **后端 WS 协议扩展**：为 `locked`、`unlocked`、`deleted`、`rolled_back` 增加可选 `ref` 以支持 Promise 式主动接口；新增 `focus {entity_id: null}` 语义用于清除当前在场位置。
- 引入 CodeMirror 6 依赖，用于 `script`/`code` 等代码类编辑器。

## Capabilities

### New Capabilities

- `editor-workspace`: 覆盖前端编辑器主界面行为，包括三段布局、实体浏览器、多标签编辑器、操作栏、右侧工具面板、锁/在场展示、实体 store 与通讯层对接。

### Modified Capabilities

- `entity-sync`: WS 协议增加 `clear_focus`（或以 `focus {entity_id: null}` 清除位置）语义，并为 `locked`/`unlocked`/`deleted`/`rolled_back` 消息补充可选 `ref` 回传。
- `file-storage`: 新增文件列表 API `GET /api/files`，返回全部文件元数据。

## Impact

- `apps/web/`：新增布局、实体浏览器、编辑器组件、工具面板、stores、`client/` 通讯层；修改路由与 HomeView。
- `apps/server/`：新增 `GET /api/files`；扩展 `ws/hub.ts` 处理 `clear_focus`/null focus 与消息 `ref`。
- `packages/puzzle-schema/`：更新 `sync.ts` 消息类型；必要时补充文件列表响应类型。
- 依赖：`apps/web` 增加 `codemirror`、`@codemirror/lang-python` 等。
- 文档：归档后同步 `entity-sync`、`file-storage` 主 specs，更新 `docs/handoff.md` 与 `README.md`。