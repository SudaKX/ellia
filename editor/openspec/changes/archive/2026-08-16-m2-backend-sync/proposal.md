## Why

`docs/plan-v2.md` 已定稿模块数据与同步的后端设计（实体模型、双计数器历史、字段锁、WS v2 协议、文件系统），但服务端目前只有 M0 的 WS echo 与 M1.1 的认证/管理 API。编辑器多人协作需要后端先成为“权威状态源”：项目、实体、历史、锁与文件全部可经 REST/WS 验证，前端编辑器才能在此基础上搭建。

## What Changes

- 新增 `projects` 表（migration v2）与项目 CRUD REST API：`GET/POST /api/projects`、`GET/PATCH /api/projects/:id`，全部挂 `requireAuth`；`module_id` 唯一校验复用 `@ellia/puzzle-schema` 的 `isValidModuleId`。
- 新增 migration v3：`entities`、`entity_history`、`files`、`app_meta` 四表；entities 采用通用行 + JSON state，元数据含 `group/kind/ui_kind/resource_id` 与双计数器 `revision/version`。
- 以 `docs/plan-v2.md` §6 为准重写 `apps/server/src/ws/hub.ts`：**BREAKING**——M0 echo 协议替换为 WS v2（`join/sync/create/patch/delete/rollback/history/lock/unlock/focus/presence/ping`），连接经 cookie 会话认证并按项目建房间。
- 实现内存态字段锁与 focus 在场记录：data_path 格式 `<entity_id>@<root>:<json_path>`，每连接 1 把锁、patch 提交后自动释放、断线按连接清理；重连采用 revision 向量全量同步。
- 实现实体服务层：create/patch/delete/rollback/history 的事务规则（entity_history 每实体 ≤ N 条快照，N 建库时固化进 app_meta；删除为物理删除并级联清历史；回退 version-1 且 revision 单调递增）。
- 新增独立文件系统：`POST/GET/DELETE /api/files`（raw bytes 上传/下载/手动删除），文件数据写 `FILE_DATA_DIR/<uuid>`，元数据入 `files` 表；上传计算 sha256 与 size，手动删除无条件生效（不检查悬空引用）。
- 新增实体 kind：容器 `file-tree`、`progress-dag`（`ENTITY_KINDS` 共 16 种）；`asset` 与 file-reference 合并为单一实体——`state = {file_id, media_type}`、resource_id 为 `asset-path:<相对路径>`（对齐 mythos `FileReference`），file-tree-node/hint 仍通过 entity id 引用 asset，多个 asset 可复用同一 `file_id`；`file-tree`/`progress-dag` 承载全部拓扑（`children`/`successors`），节点实体只存节点数据。
- 更新共享包 `@ellia/puzzle-schema`：**BREAKING**——`types.ts` 的 `Entity` 改为 v2 元数据 + 双计数器（去 `deleted`/`resource_namespace`，`AssetState` 合并为 `{file_id, media_type}`、新增 `FileTreeState`/`ProgressDagState`、`FileTreeNodeState`/`ProgressNodeState` 去拓扑化）；`sync.ts` 升级 `SYNC_PROTOCOL_VERSION=2` 并补齐 v2 消息全集。
- `.env`/`ServerConfig` 新增 `FILE_DATA_DIR`、`MAX_FILE_BYTES`、`ENTITY_HISTORY_LIMIT`。
- 后端单元测试覆盖：projects CRUD、实体 create/patch/delete/rollback/history、锁冲突与断线清理、重连全量同步、文件上传下载与 409 保护。

## Capabilities

### New Capabilities

- `projects`: 项目表与项目 CRUD REST API（登录用户全局可见可编辑；module_id 校验与唯一性）。
- `entity-sync`: 实体数据模型（kind/ui_kind/resource_id/group、revision/version、entity_history）、WS v2 同步协议（认证、房间、全量重连、增量广播）、字段锁与 focus 在场。
- `file-storage`: 独立文件系统 REST 端点、files 元数据表、磁盘 UUID→bytes 存储与手动删除规则。

### Modified Capabilities

（无。`user-management` 与 `auth-web` 的既有行为不变；`/api/health` 仅更新 `sync_protocol_version` 数值，属于实现细节。）

## Impact

- 后端 `apps/server`：`db/migrations.ts` 增加 v2/v3；`ws/hub.ts` 重写并新增项目房间/锁管理器；新增 `services/{projects,entities,files}.ts`、`routes/{projects,files}.ts`；`config.ts`、`.env.example` 扩展。
- 共享包 `packages/puzzle-schema`：`types.ts`、`sync.ts`、`validate.ts`（resource_id/group/data_path 解析校验）更新；`exporter/` 不变（导出仍延后）。
- 前端 `apps/web`：本 change 不实现编辑器 UI；共享类型变更后需保证 `pnpm type-check`/`pnpm build` 仍通过（当前前端未消费 Entity 类型，预期无代码改动；如编译受影响仅做最小适配）。
- 依赖：无新增第三方依赖（`ws`、`better-sqlite3` 已就绪）。
- 测试：`apps/server/tests` 增补 WS 测试客户端辅助工具与上述用例；`pnpm --dir apps/server test` 保持全绿。
- 文档：`docs/handoff.md` 与 `README.md` 的里程碑状态在实施后更新（本 change 仅规划）。
