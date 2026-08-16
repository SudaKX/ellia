## Context

- 后端现状（M1.1 已归档）：Express 5 + 原生 `ws`；better-sqlite3 单连接（`getDatabase()`）；migration v1 只有 `users/invite_codes/sessions`；`hub.ts` 是 M0 echo；统一 REST 错误 `{error:{code,message}}`；测试用 `:memory:` 数据库 + node:test。
- 本 change 的目标行为来自 `docs/plan-v2.md` §3–§7（实体模型、双计数器历史、锁、WS v2、文件系统）与 §10 的 M1.2/M2 后端范围；动机见 proposal.md。
- 约束：不新增第三方依赖；共享类型只在 `@ellia/puzzle-schema` 维护；前端不随本 change 实现功能，但 workspace 的 `pnpm type-check` 必须保持通过。

## Goals / Non-Goals

**Goals**

- 后端一次闭环：projects CRUD（M1.2）+ 实体/历史/锁/WS v2/文件系统（M2），全部有自动化测试。
- 所有实体变更走单一权威路径（WS + SQLite 事务），锁与版本规则在服务端强制执行。
- 文件系统与实体系统仅通过 `asset` 实体 state 中的 `file_id` 字符串连接，互不触发对方行为。

**Non-Goals**

- 前端编辑器 UI、`ui_kind` 组件实现（后续前端 change）。
- Python 包导出、`deploy_baseline` 的实际合并逻辑（仅存储字段）。
- 文件自动 GC、锁 TTL、多进程/多实例部署、WS 消息分片。
- 跨实体引用校验（如 `credit_id` 已注册、拓扑中的 stable_id（children/successors）、`file_id` 悬空）不在本 change 强制，后续前端切片再补。

## 目标文件结构

```
apps/server/src/
  config.ts                 # ServerConfig +3：fileDataDir/maxFileBytes/entityHistoryLimit
  db/
    database.ts             # 不变
    migrations.ts           # +migration v2、v3（DDL 见下）
    meta.ts                 # app_meta 读写；启动时固化 entity_history_limit
  services/
    projects.ts             # projects 表查询 + create/list/get/update
    entities.ts             # entities/entity_history 查询 + create/patch/delete/rollback/history 事务
    files.ts                # files 表查询 + 引用扫描（手动删除保护）
  routes/
    projects.ts             # /api/projects*
    files.ts                # /api/files*（express.raw）
  ws/
    hub.ts                  # upgrade 认证 + 消息分派（替换 echo）
    rooms.ts                # projectId → connections 房间表
    locks.ts                # 字段锁 Map（每连接 1 把）
    presence.ts             # focus Map + presence 聚合广播
  app.ts                    # 挂载 projects/files 路由
  index.ts                  # 不变（attachWebSocketHub 接口保持）
tests/
  helpers.ts                # +startTestServerWithWs / wsLogin / wsRequest 辅助
  projects.test.ts          # projects CRUD
  entities.test.ts          # 实体事务与历史规则（直连 DB 级 + WS 级）
  sync.test.ts              # join/sync/patch/lock/rollback/delete/presence
  files.test.ts             # 上传/下载/删除/409/上限
```

共享包：

```
packages/puzzle-schema/src/
  types.ts     # Entity/EntityRecord v2、UI_KINDS、RESOURCE_NAMESPACES、KindStateMap 调整
  sync.ts      # SYNC_PROTOCOL_VERSION=2，C→S/S→C 消息全集
  validate.ts  # parseResourceId / isValidGroup / parseDataPath / uiKindFor(kind)
```

## 表设计（migration v2/v3）

v2（M1.2）：

```sql
CREATE TABLE projects (
  id              TEXT PRIMARY KEY,
  module_id       TEXT NOT NULL UNIQUE COLLATE NOCASE,
  display_name    TEXT NOT NULL,
  description     TEXT,
  deploy_baseline TEXT,
  created_by      TEXT NOT NULL REFERENCES users(id),
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
```

v3（M2）：

```sql
CREATE TABLE entities (
  id          TEXT PRIMARY KEY,
  project_id  TEXT NOT NULL REFERENCES projects(id),
  group       TEXT NOT NULL,
  kind        TEXT NOT NULL,
  ui_kind     TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  revision    INTEGER NOT NULL,
  version     INTEGER NOT NULL,
  state       TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_entities_resource ON entities(project_id, resource_id);
CREATE INDEX idx_entities_group ON entities(project_id, group, kind);

CREATE TABLE entity_history (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_id  TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  version    INTEGER NOT NULL,
  state      TEXT NOT NULL,
  author_id  TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  UNIQUE(entity_id, version)
);
CREATE INDEX idx_entity_history ON entity_history(entity_id, version DESC);

CREATE TABLE files (
  id            TEXT PRIMARY KEY,
  original_name TEXT,
  media_type    TEXT NOT NULL,
  size          INTEGER NOT NULL,
  sha256        TEXT NOT NULL,
  uploaded_by   TEXT NOT NULL REFERENCES users(id),
  created_at    TEXT NOT NULL
);

CREATE TABLE app_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

migration v3 只建表；`app_meta['entity_history_limit']` 在 `initDatabase` 后的启动流程里“不存在则写入当前 env 值”，运行时一律读 meta。

## Decisions

### D1. projects 路由与并发唯一性

`POST /api/projects` 先 `isValidModuleId` 校验，再 `INSERT`；依赖 `module_id UNIQUE COLLATE NOCASE` + `isSqliteConstraintError` 把竞态转为 `409 RESOURCE_CONFLICT`，不做先查后插（避免 TOCTOU）。`PATCH` 仅接受 `display_name/description/deploy_baseline`，出现 `module_id` 直接 `400 VALIDATION`（创建后不可改名，规避 WS 房间路由与导出引用的连锁更新）。

### D2. 实体表通用行 + JSON state（沿用 plan-v2）

16 种 kind 共享一张表与同一套 revision/version/锁/历史机器；kind 差异只在 `state`。不用分表：同步协议按 entity_id 无关 kind，分表要 16 倍分派；不用 `json_extract` 建索引：热路径查询只用普通列（project_id/kind/group/resource_id），项目内全量加载后 JS 比较即可。

节点与拓扑分离：`file-tree-node`/`progress-node` 是纯节点数据容器，不含 parent/successors；`file-tree`（`{root_stable_id, children}`）与 `progress-dag`（`{entry_stable_ids, successors}`）持有全部拓扑。容器按约定每项目各一个（resource_id 建议 `file-tree:main`/`progress-dag:main`），但服务端**不强制数量**、不校验拓扑中 stable_id 是否存在（悬空允许，与“不做跨实体引用校验”一致）。

### D3. revision / version 双计数器与历史不变量

- `revision`：服务端分配的单调锚点，任何变更 +1。
- `version`：谱系指针，普通 patch +1、rollback -1。
- 历史行以 `UNIQUE(entity_id, version)` 保证“rollback 查 `version-1` 必有且唯一”。不变量成立的条件是**先消费后写入**：
  - patch：`INSERT history(version=当前)` → 修剪超过 N 的最旧行 → 应用 → `version++, revision++`；
  - rollback：`DELETE history WHERE version = 当前version - 1` → 应用其 state → `version--, revision++`。
- 全部在 `better-sqlite3` 同步事务里完成；单进程单连接天然全序，无需显式行锁。

### D4. WS 架构：hub + rooms + locks + presence 四模块

```
upgrade 事件
 → 解析 /ws/projects/:id
 → parseSessionCookie → findSessionWithUser（复用 M1.1）
 → 项目存在性检查
 → handleUpgrade，ws 上下文 = {connectionId, userId, username, projectId}
message 事件
 → JSON.parse（失败 error BAD_JSON）
 → 按 type 分派到实体操作处理器（join/create/patch/...）
 → 每个处理器内部直接调 services/entities 事务
 → 完成后 locks/presence/rooms 负责释放与广播
close 事件
 → locks.releaseByConnection / presence.clear / rooms.remove
```

- 不引入消息队列：Node 事件循环 + 同步 better-sqlite3 调用保证单房间内“先到先应用”，与 LWW 兜底一致。
- 心跳：客户端 30s ping，服务端 90s 无消息关闭（常量放 `hub.ts`，不进 .env）。

### D5. 锁与 data_path

锁键 = data_path 原串：`<entity_id>@state:<json-pointer>`、`<entity_id>@group:`、`<entity_id>@resource_id:`。`locks.ts` 维护：

```
locks: Map<lockKey, {connectionId, userId, username, acquiredAt}>
locksByConnection: Map<connectionId, Set<lockKey>>
```

规则实现为四步：同连接同路径幂等；同连接新路径先释放旧锁；他人持有 → `lock_denied`（含 holder）；`patch` 校验 `locks.get(data_path).connectionId === 本连接`，成功或校验失败后都释放并广播 `unlocked`。`delete/rollback` 前扫描 `locksByConnection` 是否有人锁了该实体的任何路径（锁键前缀匹配 `<entityId>@`），有则 `ENTITY_LOCKED`。锁无 TTL（plan-v2 §5.3）；断开与重启清空，前端重连重锁。

### D6. join/sync 的全量 diff

`join` 处理器：`SELECT * FROM entities WHERE project_id=?`，在 JS 中与 `vector` 比较：缺失或 revision 不同 → 全量 EntityRecord；vector 有而 DB 无 → `removed_ids`。不存服务器端向量副本；客户端是向量唯一来源。同步体量大时先单消息发送（项目规模预计可控），分片留待需要时再做。

### D7. 物理删除与广播

`delete` 直接 `DELETE FROM entities`（`entity_history ON DELETE CASCADE`）。广播 `deleted {entity_id}` 不带 revision——实体已不存在，revision 无意义；重连由 `removed_ids` 兜底。删除后同 `resource_id` 重建是全新实体（新 id、revision=1、version=1）。

### D8. 共享包类型与协议升级

- `sync.ts` 升 `SYNC_PROTOCOL_VERSION=2`；`hello` 携带 `protocol_version`。
- `types.ts` 的 `Entity` 直接改为 v2 形状（**BREAKING**，仓库内唯一消费方是本 change 的服务端与未来前端；当前前端未 import，改动安全）。
- `validate.ts` 新增纯函数：`parseResourceId`（第一个 `:` 分割，前缀∈目录、id 无 `:`/空白）、`isValidGroup`、`parseDataPath`（root 三选一，state 用 JSON Pointer）、`allowedUiKinds(kind)`。
- kind→namespace、kind→ui_kind 两张映射表放在 `types.ts`，服务端与未来前端共用同一事实源；新增映射：`file-tree → ui_kind/namespace file-tree`；`progress-dag → ui_kind/namespace progress-dag`。`asset` state 合并为 `{file_id, media_type}`（file-reference 并入 asset，路径由 `asset-path:<相对路径>` 承载）；新增 `FileTreeState {root_stable_id, children}`、`ProgressDagState {entry_stable_ids, successors}`；`FileTreeNodeState` 移除 parent 挂接、`ProgressNodeState` 移除 `successors`/`is_entry`。

### D9. 文件端点、asset 合并与存储

- `app.use('/api/files', filesRouter)`；路由内 `express.raw({type: () => true, limit: config.maxFileBytes})`，避免全局 `express.json()` 影响二进制上传。50 MiB 上限下整段缓冲进内存可接受（简单、便于一次算 sha256），不做流式写盘。
- 落盘：`FILE_DATA_DIR/<uuid>`，先写 `<uuid>.tmp` 再 `rename`（原子性）；目录不存在时 `mkdir -p`。
- 手动删除：**无条件**先 `DELETE files` 行提交，再 `unlink` 磁盘文件；不存在 → `404 FILE_NOT_FOUND`；`unlink` 失败仅记日志并仍返回 204（元数据已删，磁盘残留可后续人工清理）。不做任何 `entities`/`entity_history` 扫描，删除后可能出现悬空 `file_id`（specs/file-storage 明确允许）。
- 文件与实体世界的连接点为 `asset` 实体（file-reference 已并入 asset，语义对齐 mythos `FileReference(module, relative_path, media_type)`，上游定义见 `mythos/src/mythos/registry/files/definitions.py`）：
  - `asset.state = {file_id, media_type}`；`resource_id = asset-path:<规范相对路径>`（复用 mythos `is_canonical_source_relative_path` 规则：非空、不以 `/` 开头、无 `\`/`:`、无 `.`/`..` 段）；路径是**逻辑身份**，替换内容时 resource_id 不变；
  - patch `state.file_id` / `state.media_type` 均走字段锁，`entity_history` 保存旧 state（回退可恢复旧引用，前提是旧文件未被手动删除）；
  - file-tree-node / hint 仍通过 `source_asset_id`（entity id）引用 asset；多个 asset 可持有同一 `file_id`（复用同一份字节，服务端不做独占校验）；
  - 创建与 patch 不校验 `file_id` 是否存在于 files 表（悬空允许，与“不做悬空检查”一致）；
  - 删除 asset 实体不触碰 files 行与磁盘字节；文件数据只能由文件端点删除。

### D10. 测试策略

- `helpers.ts` 新增 `startTestServerWithWs()`：`createServer(createApp(config))` + `attachWebSocketHub`，返回 `baseUrl`/`wsUrl`。
- WS 测试用 Node 24 内置 `WebSocket` + `node:events` 的 `once(ws,'message')`，封装 `wsRequest(ws, message)` 与“等待指定 type”辅助；登录 cookie 复用现有 `loginCookie`，连接时放 `Cookie` 头。
- 实体服务层先做直连 DB 的纯事务测试（revision/version/历史不变量、asset 文件引用形状与共享 file_id），再做 WS 端到端（锁冲突、广播、重连 diff、断线清理）。
- 文件测试使用 `mkdtemp` 临时目录作为 `FILE_DATA_DIR`，测试后清理。

## Risks / Trade-offs

- [大 `sync` 消息可能撑大单帧] → 当前项目规模小；预留：超出阈值时客户端重新 join 前可先按 group 拉取，或后续引入分片消息。
- [锁无 TTL，用户挂机锁字段] → 失焦/unlock/断线已覆盖主路径；后续加惰性过期不改协议，只改 locks.ts。
- [手动删除文件可能使 asset/历史快照悬空] → 契约明确允许悬空；前端后续以 `FILE_NOT_FOUND` 呈现缺失文件，回退到的旧 file_id 若被删则同样按缺失处理。
- [50 MiB 文件整段进内存] → 上限可配小；后续可换流式写盘 + 边写边哈希，端点契约不变。
- [实体 state 校验是轻量结构校验，不查跨实体引用] → 与 plan-v2“导出不校验、字段覆盖即可”一致；引用完整性留到编辑器表单/未来 change。
- [单进程内存态锁在多实例下失效] → v1 明确单实例；部署文档注明，多实例需共享锁服务（非本版目标）。

## Migration Plan

1. 发布代码后首次启动自动执行 migration v2（projects）与 v3（entities/entity_history/files/app_meta）；既有 v1 库无损升级，仅新增表与索引。
2. 启动流程在迁移后调用 `meta.ensureSeeded(config)`：`app_meta` 无 `entity_history_limit` 时写入当前 env 值；之后 env 修改不再生效（符合“建库后固定”）。
3. 无 down migration：如需回滚，在升级前备份 `data/ellia.db`；回滚代码后新增表闲置不影响旧功能，重建库即可恢复干净状态。
4. `SYNC_PROTOCOL_VERSION` 2 上线后，旧前端（M0 echo 客户端）与新版 WS 不兼容；当前无生产客户端，不提供兼容层。

## Open Questions

（均可延后回答，不影响本 change 的 specs 与任务拆分）

- 项目规模增大后 `sync` 是否按 group 分片发送？
- `file-tree`/`progress-dag` 未来是否按 group 各建一个容器（本 change 约定每项目一个且不强制）？
- 锁是否需要 TTL/续期心跳？
- 文件引用扫描是否需要专用索引表？
