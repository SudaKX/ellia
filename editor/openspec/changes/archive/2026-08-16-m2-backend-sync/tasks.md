## 1. 共享包与配置

- [x] 1.1 `packages/puzzle-schema/src/types.ts`：将 `Entity` 改为 v2 形状（`id/project_id/group/kind/ui_kind/resource_id/revision/version/state/created_at/updated_at`，移除 `deleted` 与 `ref`），新增 `EntityRecord` 同步载荷、`FileTreeState {root_stable_id, children}`、`ProgressDagState {entry_stable_ids, successors}`；`AssetState` 合并为 `{file_id, media_type}`；`FileTreeNodeState` 移除 parent 仅存节点数据；`ProgressNodeState` 移除 `successors`/`is_entry`；`ENTITY_KINDS` 为 16 种（含 `file-tree`/`progress-dag`，无独立 file-reference）
- [x] 1.2 `types.ts` 新增 `UI_KINDS` 目录、`RESOURCE_NAMESPACES` 目录及 `uiKindFor(kind)`、`namespaceFor(kind)` 两张映射表（plan-v2 §3.3/§3.4），包含新 kind 映射：`file-tree → ui_kind file-tree / namespace file-tree`、`progress-dag → ui_kind progress-dag / namespace progress-dag`；asset 的 namespace 为 `asset-path`
- [x] 1.3 `packages/puzzle-schema/src/sync.ts`：`SYNC_PROTOCOL_VERSION` 升为 2，定义 v2 全部 C→S/S→C 消息类型（join/create/patch/delete/rollback/history/lock/unlock/focus/ping、hello/sync/created/applied/update/deleted/rolled_back/history/locked/unlocked/lock_denied/presence/error/pong），`hello` 携带 `protocol_version`
- [x] 1.4 `packages/puzzle-schema/src/validate.ts`：新增 `parseResourceId`（首个 `:` 分隔、前缀/id 规则，`asset-path` 的 id 校验规范相对路径）、`isValidGroup`、`parseDataPath`（root ∈ state/group/resource_id，state 用 JSON Pointer）、`allowedUiKinds(kind)`，并从包入口导出
- [x] 1.5 `apps/server/src/config.ts` 与 `.env.example`：新增 `FILE_DATA_DIR`、`MAX_FILE_BYTES`、`ENTITY_HISTORY_LIMIT`（校验 ≥1 整数），同步更新 `testConfig()` 用到的类型
- [x] 1.6 运行 `pnpm type-check` 确认 workspace（含未改动前端）通过，修复共享类型变更导致的编译问题

## 2. 数据库迁移与元数据

- [x] 2.1 `db/migrations.ts` 增加 migration v2：`projects` 表（含 `module_id UNIQUE COLLATE NOCASE` 与索引）
- [x] 2.2 `db/migrations.ts` 增加 migration v3：`entities`/`entity_history`/`files`/`app_meta` 四表与索引（含 `entity_history ON DELETE CASCADE`、`UNIQUE(entity_id, version)`、`UNIQUE(project_id, resource_id)`）
- [x] 2.3 新增 `db/meta.ts`：`ensureMetaSeeded(config)` 在 `entity_history_limit` 缺失时写入 env 值；`getEntityHistoryLimit()` 只读 app_meta
- [x] 2.4 `index.ts` 启动流程调用 `ensureMetaSeeded`，并确保 `FILE_DATA_DIR` 目录存在

## 3. 项目 CRUD（M1.2 后端）

- [x] 3.1 新增 `services/projects.ts`：create/list/get/update 查询与行→`Project` 映射；唯一约束冲突转换为 409 `RESOURCE_CONFLICT`
- [x] 3.2 新增 `routes/projects.ts`：`GET/POST /api/projects`、`GET/PATCH /api/projects/:id`，全部挂 `requireAuth`；创建校验 `isValidModuleId`；PATCH 拒绝 `module_id` 并只接受 `display_name/description/deploy_baseline`
- [x] 3.3 `app.ts` 挂载 `/api/projects` 路由
- [x] 3.4 新增 `tests/projects.test.ts`：成功创建、重复 module_id 409、非法 module_id 400、列表按 updated_at 降序、详情 404、PATCH 成功与 module_id 不可改、未登录 401

## 4. 实体服务层

- [x] 4.1 新增 `services/entities.ts`：`EntityRow` 类型、`toEntityRecord` 映射、`createEntity`（校验 16 种 kind、ui_kind/resource_id 及按 kind 的 state 形状：asset 为 `{file_id, media_type}`、file-tree 为 `{root_stable_id, children}`、progress-dag 为 `{entry_stable_ids, successors}`、file-tree-node/progress-node 不含拓扑字段等；revision=1、version=1）
- [x] 4.2 实现 `applyDataPath`：JSON Pointer 读取/写入 `state`，容器整体替换；`@group:`/`@resource_id:` 读写元数据列
- [x] 4.3 实现 `patchEntity` 事务：插入当前 state 到 `entity_history`（旧 version）→ 按 N 修剪最旧行 → 应用 data_path → `version+1`、`revision+1`
- [x] 4.4 实现 `rollbackEntity` 事务：读取并删除 `version-1` 快照 → 应用其 state → `version-1`、`revision+1`；无快照时抛 `HISTORY_EMPTY`
- [x] 4.5 实现 `deleteEntity`：物理删除 + 历史级联清除
- [x] 4.6 实现 `listHistory`（version 降序）与 `listProjectEntities`（供 join/sync 全量 diff）
- [x] 4.7 新增 `tests/entities.test.ts`（直连 DB 层）：revision 单调、version 回退递减、历史不变量 `UNIQUE(entity_id, version)`、N 修剪、删除级联、同 resource_id 删除后重建、@group/@resource_id patch 规则、asset 悬空 file_id 允许创建、多个 asset 共享 file_id、file-tree/progress-dag 容器拓扑与节点数据分离

## 5. WS 基础设施与协议处理器

- [x] 5.1 新增 `ws/rooms.ts`：项目房间 `Map<projectId, Set<connection>>`，join/leave/broadcast 原语
- [x] 5.2 新增 `ws/locks.ts`：`locks` 与 `locksByConnection` 两 Map；同连接幂等/顶替、他人拒绝、按连接释放、按实体前缀扫描（供 delete/rollback 的 `ENTITY_LOCKED` 判断）
- [x] 5.3 新增 `ws/presence.ts`：focus Map（连接级）与 presence 聚合广播（同用户多连接取最近一条）
- [x] 5.4 重写 `ws/hub.ts`：upgrade 阶段 cookie 会话认证 + 项目存在性校验；连接上下文 `{connectionId,userId,username,projectId}`；JSON 解析失败回 `error BAD_JSON`；30s/90s 心跳超时
- [x] 5.5 实现 `join`/`sync`：按 vector 比较项目全量实体，revision 不一致或缺发全量 `EntityRecord`，vector 多余实体归入 `removed_ids`
- [x] 5.6 实现 `create` 处理器：校验与落库、`created` 应答 + 房间广播
- [x] 5.7 实现 `lock`/`unlock` 处理器：`locked`/`lock_denied`（含持有者）/`unlocked` 广播
- [x] 5.8 实现 `patch` 处理器：锁持有者校验（`STALE_LOCK`）→ `patchEntity` 事务 → `applied`（提交者）→ `update`（房间广播）→ 释放锁并广播 `unlocked`
- [x] 5.9 实现 `delete`/`rollback`/`history` 处理器：他人锁检查（`ENTITY_LOCKED`）、`deleted`/`rolled_back`/`history` 消息
- [x] 5.10 实现 `focus`/`ping` 处理器与 close 清理：断开时释放连接锁、清除 focus、移出房间并广播 presence

## 6. WS 端到端测试

- [x] 6.1 扩展 `tests/helpers.ts`：`startTestServerWithWs()`（http server + `attachWebSocketHub`）、`wsConnect`（带 Cookie）、`wsRequest`、`waitForMessage`
- [x] 6.2 新增 `tests/sync.test.ts`：未登录/项目不存在拒绝升级；join 全量与增量 diff、removed_ids；create 广播；patch 的 applied/update；锁冲突/幂等/顶替/断线清理；STALE_LOCK；group/resource_id patch；delete 的 ENTITY_LOCKED 与删除后重建；rollback 广播与 HISTORY_EMPTY；history 查询；focus/presence；ping/pong；BAD_JSON；asset 创建、多个 asset 共享 file_id、file_id patch 后回退恢复旧引用；file-tree/progress-dag 容器创建与 children/successors 整容器加锁 patch

## 7. 文件系统后端

- [x] 7.1 新增 `services/files.ts`：files 表 insert/get/delete；删除为无条件删除，不扫描 entities/entity_history
- [x] 7.2 新增 `routes/files.ts`：`POST /api/files`（`express.raw`、limit=MAX_FILE_BYTES、计算 sha256/size、临时文件+rename 原子落盘）；`GET /api/files/:file_id`（字节流 + `Content-Type`/`X-Original-Name`/`X-File-Sha256`/`X-File-Size`）；`DELETE /api/files/:file_id`（存在则删行+unlink 返回 204，不存在 404；不做引用检查）
- [x] 7.3 `app.ts` 挂载 `/api/files`；文件端点全部 `requireAuth`
- [x] 7.4 新增 `tests/files.test.ts`（临时 FILE_DATA_DIR）：上传元数据与 sha256、下载一致性、413 上限、404、手动删除 204 且不检查引用（悬空允许）、未登录 401、上传不触发实体版本变化

## 8. 集成验证与文档

- [x] 8.1 运行 `pnpm install --frozen-lockfile`、`pnpm type-check`、`pnpm build`、`pnpm --dir apps/server test`，修复全部失败
- [x] 8.2 本地冒烟：启动服务 → curl 创建项目 → WS 脚本完成 join/create/lock/patch/rollback/delete → 上传文件并创建 asset（悬空允许）与多个 asset 共享 file_id → 手动删除文件验证悬空接受 → 重启服务验证 app_meta N 固化与文件持久化
- [x] 8.3 更新 `docs/handoff.md`：M1.2 与 M2 后端状态、新表/端点/WS 协议 v2、新配置项与手动测试要点
- [x] 8.4 更新 `README.md` 里程碑状态（M1.2 完成、M2 后端完成，前端编辑器待办）
- [x] 8.5 运行 `openspec validate m2-backend-sync` 确认 change 有效
