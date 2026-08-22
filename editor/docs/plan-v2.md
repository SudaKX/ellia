# Ellia 谜题在线多人编辑器 — 模块数据与同步 v2 方案（plan-v2）

> 状态：草案（已确认关键选项，待整体审阅）。
> 关系：在 `docs/plan-v1.md` 基础上修订 §3 数据模型、§4 同步协议、§5 REST、§8 前端、§9 里程碑。
> 与 plan-v1 冲突处以本文档为准；plan-v1 的仓库布局、认证权限、M0/M1 结论未冲突部分继续有效。
> 实施前再按本文档拆 OpenSpec change（M2），本文档不是实现。

---

## 1. v2 变更总览

### 1.1 在 v1 基础上新增

| 主题 | 内容 |
| --- | --- |
| 实体元数据 | `group`（实体分组，对应未来 puzzles 子包）、`ui_kind`（前端展示类型，创建必填）、`resource_id`（自带 `<namespace>:<id>`，项目内唯一） |
| 删除语义 | **物理删除**：删除即移除行与其历史，不做 tombstone |
| 版本计数 | 双计数器：`revision`（同步锚点，单调递增）+ `version`（谱系指针，回退可递减） |
| 并发控制 | data_path 字段锁（内存 Map）+ 用户当前位置（focus）在场记录 |
| 历史 | `entity_history` 全量状态快照表，每实体保留 N 条旧版本 |
| 文件 | 独立文件系统：UUID → bytes 落盘；`files` 表存元数据（UUID 主键）；REST 上传/下载/手动删除 |

### 1.2 简化或移除（相对 v1）

| v1 设计 | v2 处理 |
| --- | --- |
| `entity_patches` 补丁日志（{from,to} 双向值） | 移除，由 `entity_history` 快照替代 |
| 内存环形缓冲 + DB 补丁重放 + 全量三级回退 | 移除前两级；重连直接全量同步（按 revision 向量筛选） |
| `entity_blobs`（SQLite BLOB） | 移除；文件数据落本地文件系统，元数据入 `files` 表 |
| tombstone（`deleted=1` 软删除） | 移除；删除即物理移除，重连用 `removed_ids` 通知 |
| LWW `base_mismatch` 冲突提示 | 由字段锁替代；未加锁的容器整体编辑走服务器串行 LWW 兜底 |
| 项目级修改历史（plan-v2 早期讨论） | 第一版不做 |
| Python 包生成（`__init__.py` / zip 导出） | 延后；`puzzle-schema/exporter` 保持占位 |

### 1.3 范围声明（第一版 M2）

- 实体字段只需**覆盖/可推导** mythos 后端所需字段，不要求格式完全一致；后续可调整后端对齐。
- 不支持跨实体级联回退；回退仅限单个实体、手动触发、不可逆（不记 redo）。
- 孤儿文件不做自动 GC，提供**手动删除端点**（§4.5）。

---

## 2. 总体结构

```
Project（projects 表，元数据）
 └─ Entity × N（entities 表）
     ├─ 元数据列：group / kind / ui_kind / resource_id
     ├─ 双计数器：revision（同步锚点）/ version（谱系指针）
     └─ state（JSON，16 种 kind 对应 KindStateMap）

entity_history（每实体 ≤ N 条旧状态快照，仅存 state；随实体删除级联清除）
app_meta（N 等建库期固定配置）
files（UUID 主键 + 原始文件名/媒体类型/size/sha256/上传者/时间）→ 磁盘 data/files/<uuid>

通道：
  WS  /ws/projects/:id —— 实体全部同步操作（create/patch/delete/rollback/history/lock/focus）
  REST /api/*          —— auth、admin、projects CRUD、文件上传/下载/删除
```

---

## 3. 数据模型

### 3.1 entities 表（migration v3）

```sql
entities(
  id           TEXT PRIMARY KEY,          -- 内部 UUID
  project_id   TEXT NOT NULL REFERENCES projects(id),
  group        TEXT NOT NULL,             -- 实体分组，默认 'main'
  kind         TEXT NOT NULL,             -- 后端实体种类（16 种之一）
  ui_kind      TEXT NOT NULL,             -- 前端展示类型（目录见 §3.3，创建必填）
  resource_id  TEXT NOT NULL,             -- 业务身份，格式 <namespace>:<id>，项目内唯一
  revision     INTEGER NOT NULL,          -- 同步锚点，单调递增，永不回退
  version      INTEGER NOT NULL,          -- 谱系指针，更新+1/回退-1
  state        TEXT NOT NULL,             -- JSON：权威当前状态
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);

CREATE UNIQUE INDEX idx_entities_resource
  ON entities(project_id, resource_id);
CREATE INDEX idx_entities_group ON entities(project_id, group, kind);
```

- **物理删除**：`DELETE` 直接移除行；`entity_history` 通过 `ON DELETE CASCADE` 一并清除。
- `resource_id` 项目内**全局唯一**，唯一性作用于**完整字符串（含命名空间前缀）**：`stable-id:main` 与 `account:main` 是两个不同的 resource_id，可以共存；同一命名空间内 id 部分不可重复。其中 `stable-id` 命名空间横跨 4 类 kind，天然满足 mythos「stable_id 全项目唯一」的硬约束。
- 删除后重建同名 `resource_id` 自然可行（旧行已不存在）。

### 3.2 kind（后端语义）目录

沿用并扩展 `@ellia/puzzle-schema` 的 `ENTITY_KINDS` 至 16 种，**kind 只归后端使用**：

```
progress-node / file-node / file-tree / progress-dag / asset /
hint / script / validation / artifact / artifact-node / account /
credit / achievement / task / listener / code
```

### 3.3 ui_kind（前端展示类型）目录

`ui_kind` 指导前端选择渲染组件，与 kind 解耦。第一版目录：

| ui_kind | 渲染组件 | kind 映射 |
| --- | --- | --- |
| `dag-node` | 进度 DAG 节点表单 | progress-node |
| `file-tree` | 文件树结构编辑器（根/父子排序） | file-tree |
| `progress-dag` | DAG 结构编辑器（入口与边） | progress-dag |
| `asset` | 文件引用 + 内容预览 | asset |
| `script` | 脚本表单（含 CodeMirror 行编辑） | script |
| `code` | 纯代码编辑器（Python） | code |
| `form` | 通用结构化表单（schema 由 kind 驱动） | hint / validation / artifact / artifact-node / account / credit / achievement / task / listener |

规则：

- **创建实体的 `create` 消息必须显式携带 `ui_kind`**，服务端校验其属于该 kind 的允许值，否则 400。
- 前端维护 `ui_kind → 组件` 注册表；运行时遇到未知 `ui_kind`（未来新增 kind 的兜底）回退到 `form` + 只读 JSON 预览。
- 后端新增 kind 时只需在共享包登记 kind → ui_kind 映射；前端创建表单按映射自动选中、显式发送。

### 3.4 resource_id（自带命名空间）

- 格式：`<namespace>:<id>`，**命名空间前缀是 resource_id 的一部分**，不单独建列。
- 解析规则：以**第一个 `:`** 分隔；`id` 部分不允许再含 `:`、不允许空白；整体 ≤128 字符。
- 服务端按 kind 校验前缀必须是下表对应命名空间；唯一性作用于完整 `resource_id` 字符串（§3.1 唯一索引）——不同命名空间因前缀不同不会互斥，同一命名空间内 id 部分不可重复。

| namespace | 包含 kind | 校验 |
| --- | --- | --- |
| `stable-id` | hint / script | id 非空、无空白 |
| `validation` | validation | id 非空、无空白 |
| `file-tree` | file-tree | id 非空、无空白 |
| `progress-dag` | progress-dag | id 非空、无空白 |
| `asset` | asset | id 非空、无空白 |
| `artifact` | artifact | id 非空、无空白 |
| `inode` | artifact-node / file-node | id 非空、无空白 |
| `pnode` | progress-node | id 非空、无空白 |
| `account` | account | id 非空、无空白 |
| `credit` | credit | id 非空、无空白 |
| `achievement` | achievement | id 非空、无空白 |
| `task` | task | id 非空、无空白 |
| `listener` | listener | id 非空、无空白 |
| `code` | code | id 满足 `isPythonName` |

说明：

- `listener` 通过 `listener:<id>` 获得显式身份（前端自动建议 `evt_<event_type>_<priority>`，用户可改）。
- `validation` 的 id 部分 = stable_id；其 `validation_id` 仍按 slug 规则校验。
- `task` 的 id 部分即 mythos 的 task_id。
- `code` 的 id 部分 = 函数名，保证导出为模块级函数时不撞名。
- 前端创建表单固定展示前缀、只让用户填写 id 部分；提交时由前端拼成完整 `resource_id`。
- 修改 resource_id（patch 根选择器 `resource_id`）时，新值前缀必须与当前 kind 的命名空间一致。

### 3.5 group（实体分组）

- `group` 是 entities 的普通列，不是独立表；第一版不设分组元数据。
- 格式：Python 模块路径段，`^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$`，默认 `main`。
- 前端实体树第一层按 group 分组；未来导出时一个 group 对应 puzzles 模块的一个子包。
- 修改 group 走 patch 根选择器 `group`（§5.1），与字段修改同一条锁与版本路径。

### 3.6 state（JSON）对现有类型的调整

在 `@ellia/puzzle-schema` `KindStateMap` 基础上：

| 调整 | 内容 |
| --- | --- |
| `FileTreeNodeState` | 仅节点数据：`{stable_id, display, hidden, download_name, source_asset?, access_rule?}`；不含 parent/kind/path/children/name |
| `FileTreeState`（新增 kind） | `{rootId, nodes: Record<TreeNodeId, FileTreeNode>}`：扁平节点表；`FileTreeNode` 含 `id/name/inode/parent/order` |
| `ProgressNodeState` | 仅节点数据：`{how?, mode?, triggers_checkpoint}`；移除 `successors` 与 `is_entry` |
| `ProgressDagState`（新增 kind） | `{entry_stable_ids, successors: Record<from_stable_id, to_stable_id[]>}`：DAG 全部拓扑与入口 |
| `AssetState` | `{ source_reference?, file_reference?, media_type }`；引用当前文件或后续 source，module/path 由导出时生成 |
| `EventListenerState` | 身份由列 `resource_id` 承载，state 内容不变 |
| 其他 state | 暂不修改；字段以“覆盖/可推导 mythos 所需”为准，后续可调 |

### 3.7 revision 与 version 双计数器（核心语义）

| 计数器 | 规则 | 用途 |
| --- | --- | --- |
| `revision` | 每次 create/update/delete/rollback 均 **+1**，永不回退 | 同步向量、消息乱序过滤、重连 diff 基准 |
| `version` | 正常更新 **+1**；回退 **-1** | 历史定位与 UI 显示（“回退到第几个版本”） |

时间线示例：

```
操作          revision   version   entity_history
create        1          1         —
update A      2          2         + [v1, 状态 S1]
update B      3          3         + [v2, 状态 S2]
rollback      4          2         - [v2]（应用 S2，该行被消费）
update C      5          3         + [v2, 状态 S2]（当前回退态重新入库）
```

要点：

- 客户端同步**只看 revision**，version 递减不会触发“旧消息丢弃”。
- 回退 = 应用 `entity_history` 中 `version = 当前version - 1` 的记录，并删除该记录（不可逆、无 redo）。
- 回退后再更新：当前状态以新的 version 值重新入历史，`UNIQUE(entity_id, version)` 不会冲突（被消费的行已删除）。
- 回退后连续回退：`version - 1` 的记录始终存在（谱系指针与历史行一一对应）。
- 删除实体时 revision 概念随行一起消失（物理删除），不影响任何已存在实体。

### 3.8 entity_history（历史快照表）

```sql
entity_history(
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_id  TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  version    INTEGER NOT NULL,             -- 快照对应的谱系版本
  state      TEXT NOT NULL,                -- 旧状态全量 JSON
  author_id  TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  UNIQUE(entity_id, version)
);
CREATE INDEX idx_entity_history ON entity_history(entity_id, version DESC);
```

- **只存 state，不存 revision、group、resource_id 等元数据**；审计信息用 `author_id`/`created_at`。
- 正常更新事务：`INSERT 当前(state, version)` → 若行数 > N 删除 version 最小的行 → 应用 patch → `version += 1; revision += 1`。
- 回退事务：读取并 `DELETE version = version - 1` 的行 → 应用该 state → `version -= 1; revision += 1`。
- 删除实体：删除 entities 行，entity_history 级联清除（物理删除，无 tombstone、无项目级恢复）。
- `history` 读取按 `entity_id` 查全部 ≤ N 行，version DESC 返回。

### 3.9 N 的固化（app_meta）

```sql
app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
```

- 配置项：`ENTITY_HISTORY_LIMIT`（默认 20，≥1 的整数），从 `.env` 读取。
- migration v3 建表后，启动时若 `app_meta['entity_history_limit']` 不存在，写入**当次** env 值；此后运行时只读 app_meta，改 .env 重启不生效。
- 想改 N：手动更新 app_meta（或重建库）。文档与启动日志需提示这一点。

---

## 4. 文件系统（blob 独立系统）

### 4.1 模型

- 文件数据 = 单层映射 `UUID → bytes`，存本地目录 `FILE_DATA_DIR`（默认 `data/files`），**不进 SQLite**。
- 文件内容**不可变**（write-once）：文本修改 = 上传新 bytes 得新 `file_id`，实体 patch 更新引用。
- 文件**元数据**存 SQL `files` 表（UUID 主键）：原始文件名、媒体类型、size、sha256、上传者、时间。
- 文件引用并入 `asset` 实体：`state = {source_reference?, file_reference?, media_type}`，`resource_id = asset:<id>`；file-node / hint 通过 entity id 引用 asset。多个 asset 可指向同一 `file_reference`（复用同一份字节）。

### 4.2 files 表（migration v3）

```sql
files(
  id            TEXT PRIMARY KEY,          -- UUID，即 file_id，也是磁盘文件名
  original_name TEXT,                      -- 上传时附加的原始文件名（可选）
  media_type    TEXT NOT NULL,
  size          INTEGER NOT NULL,
  sha256        TEXT NOT NULL,
  uploaded_by   TEXT NOT NULL REFERENCES users(id),
  created_at    TEXT NOT NULL
);
```

### 4.3 REST 端点

```text
POST /api/files                requireAuth
  请求体：raw bytes
  请求头：Content-Type 记录为 media_type；X-Original-Name 记录为原始文件名（可选）
  响应 201：{ file_id, original_name, media_type, size, sha256, uploaded_by, created_at }

GET  /api/files/:file_id       requireAuth
  响应：原始字节流；Content-Type=media_type；X-Original-Name / X-File-Sha256 / X-File-Size 头

DELETE /api/files/:file_id     requireAuth
  响应 204；不检查实体/历史中的悬空引用，删除即生效（悬空 file_id 允许存在）
```

- 写入：先写临时文件再原子 rename；写入过程计算 size 与 sha256；超过 `MAX_FILE_BYTES`（默认 50 MiB）返回 413。
- 上传/下载**不触碰实体版本**，也不广播——文件系统与同步系统完全分离。
- 权限：全局两层权限不变（登录 user 可访问所有项目文件），端点只做 `requireAuth`。
- 手动删除（§4.5）：无条件删除 SQL 行与磁盘文件，不做引用扫描，接受实体中出现悬空 file_id。

### 4.4 文本/二进制资产编辑流

```
下载: GET /api/files/:file_id → 本地编辑器（CodeMirror / 二进制预览）
保存: POST /api/files（新 bytes → 新 file_id + 新元数据行）
引用: WS lock(asset 的 state.file_id) → patch file_id=新值 → applied
      （entity_history 保存旧 file_id；旧文件未被手动删除时回退后仍可下载）
```

### 4.5 孤儿文件策略

- **不做自动 GC**：已上传文件只通过手动删除端点移除。
- 提供 **`DELETE /api/files/:file_id`** 手动清理：**无条件删除** SQL 行与磁盘字节，不检查悬空引用——即使存在 asset 或历史快照仍引用该 file_id，也允许删除（悬空引用由编辑器后续操作处理）。
- 删除 asset 实体不会删除 files 行与磁盘字节（两系统解耦）；文件数据只能通过文件端点删除。

---

## 5. 字段锁与在场记录（仅内存）

### 5.1 data_path 语法

```
<entity_id>@<root>:<json_path>

root ∈ { state, group, resource_id }
```

- `root=state`：`<json_path>` 为 JSON Pointer（`/display/label`、`/body/lines`、`/successors`）。文件名可能含点号，避免点路径歧义。
- `root=group` / `root=resource_id`：`<json_path>` 为空（锁的目标就是该列本身），即 `...@group:` / `...@resource_id:`。
- 示例：`<entity_id>@state:/display/label`、`<entity_id>@group:`、`<entity_id>@resource_id:`。

### 5.2 锁单元

- **叶子标量字段**（string/number/boolean）各自一把锁。
- **数组/对象整体作为一把锁**（如 `/successors`、`/display`），增删改元素都先锁整个容器。
- `group` / `resource_id` 各自一把锁。
- `kind`、`ui_kind`、`revision`、`version` 不可通过 patch 修改。

### 5.3 内存结构

```ts
// lockKey = '<entity_id>@<root>:<json_path>'
locks:             Map<lockKey, { connectionId, userId, username, acquiredAt }>
locksByConnection: Map<connectionId, Set<lockKey>>
focus:             Map<connectionId, { userId, username, entityId, dataPath?, updatedAt }>
```

- **每连接最多 1 把锁**；断线按连接清理其全部锁与 focus（不按 user_id 清理，避免多标签页互相误释放）。
- 服务重启后全部清空；客户端重连后由前端重新加锁。
- 第一版**无 TTL**：锁靠“提交 / 失焦 / 显式 unlock / 断线”释放；如后续发现长驻锁问题，再加惰性过期。

### 5.4 锁生命周期规则

1. `lock` 同一连接、同一 data_path → 幂等成功（返回当前锁信息）。
2. `lock` 同一连接、新 data_path → 自动释放旧锁，获取新锁。
3. `lock` 其他连接持有 → `lock_denied`，附持有者 `{user_id, username}`。
4. `patch` 必须携带与锁一致的 `data_path`，服务端校验锁持有者 = 本连接；未持锁或已被顶掉 → `error STALE_LOCK`。
5. `patch` 处理结束（成功或校验失败）**立即释放该锁**，并广播 `unlocked`。
6. 删除/回退：若**其他连接**在该实体任意字段持锁 → 拒绝（`error ENTITY_LOCKED`，附持有者）；本连接自己的锁随操作释放。
7. `group` / `resource_id` 的 patch 遵守同样规则；`resource_id` 新值前缀必须与 kind 的命名空间一致。

### 5.5 focus（当前位置在场）

- 客户端在**选中实体/字段聚焦/失焦**时发送 `focus {entity_id, data_path?}`，前端节流约 250ms。
- 服务端更新 `focus` Map（仅内存，不持久化），并作为 `presence` 的一部分广播：
  `{users: [{id, username, entity_id?, data_path?}]}`（同用户多连接时聚合展示最近一条）。
- 断线清除该连接的 focus；锁事件（locked/unlocked）另行广播，供前端渲染“谁在改哪个字段”。

---

## 6. WS 同步协议 v2

`@ellia/puzzle-schema` 的 `SYNC_PROTOCOL_VERSION` 升级为 `2`；`sync.ts` 按本章重写。

### 6.1 连接与认证

- 路径：`/ws/projects/:id`。
- 升级握手：从 cookie 解析 `ellia_session` → 查 `sessions` 表 → 未登录拒绝升级；项目不存在拒绝。
- 服务端维护项目房间：`Map<projectId, Set<connection>>`；所有登录 user 可访问所有项目（plan-v1 §7 不变）。
- 心跳：客户端 30s `ping`；服务端 90s 未收到任何消息关闭连接。

### 6.2 C → S 消息

| 消息 | payload |
| --- | --- |
| `join` | `{project_id, vector: {entity_id: revision}}` |
| `create` | `{ref, group, kind, ui_kind, resource_id, state}`（ui_kind **必填**） |
| `patch` | `{ref, entity_id, data_path, value}`（锁已由 lock 建立） |
| `delete` | `{ref, entity_id}` |
| `rollback` | `{ref, entity_id}` |
| `history` | `{ref, entity_id}` |
| `lock` | `{ref, entity_id, data_path}` |
| `unlock` | `{ref, entity_id, data_path}` |
| `focus` | `{entity_id, data_path?}` |
| `ping` | `{}` |

- `ref` 是提交者自定短串（如 uuid），用于把响应匹配回本地操作。
- `create.resource_id` 必须是完整 `namespace:id`；`create.state` 必须是该 kind 的合法完整 state（服务端校验）；`create` 不需要锁。

### 6.3 S → C 消息

| 消息 | payload | 触发 |
| --- | --- | --- |
| `hello` | `{service, protocol_version: 2}` | 连接建立 |
| `sync` | `{entities: EntityRecord[], removed_ids: string[]}` | join 应答 |
| `created` | `{ref, entity}` | create 应答 + 房间广播 |
| `applied` | `{ref, entity_id, revision, version}` | patch 更新确认（给提交者） |
| `update` | `{entity_id, revision, version, data_path, value, author:{id,username}}` | 广播给房间内其他人 |
| `deleted` | `{entity_id}` | delete 确认 + 广播（物理删除，无 revision） |
| `rolled_back` | `{entity_id, revision, version, state, author}` | rollback 确认 + 广播 |
| `history` | `{ref, entity_id, entries: [{version, state, author_id, created_at}]}` | history 应答 |
| `locked` / `unlocked` | `{entity_id, data_path, user?:{id,username}}` | 锁状态变化广播 |
| `lock_denied` | `{ref, entity_id, data_path, holder:{user_id,username}}` | lock 被拒 |
| `presence` | `{users: [{id, username, entity_id?, data_path?}]}` | 成员/focus 变化 |
| `error` | `{ref?, code, message}` | 任意请求失败 |
| `pong` | `{}` | ping 应答 |

`EntityRecord`（v2）：

```ts
{ id, group, kind, ui_kind, resource_id,
  revision, version, state }
```

### 6.4 join / sync（重连全量同步）

- 客户端 join 时携带本地 `vector: {entity_id: revision}`。
- 服务端对比 DB：

```
存活实体：本地无此 entity_id，或 revision 不同 → 发全量 EntityRecord
已消失实体：本地 vector 有、DB 中不存在（含被物理删除）→ 归入 removed_ids
完全一致 → 不发
```

- 客户端收到 `sync` 后，以服务端为准整体重建本地实体集合：应用 `entities`，删除 `removed_ids` 及本地多出的实体。
- **没有增量重放、没有环形缓冲、没有 tombstone**。在线期间错过消息（收到 revision > 本地已知 + 1）→ 立即重新 `join`。

### 6.5 patch / update 事务

```
接收 patch
 → 校验：实体存在、data_path 合法、锁持有者=本连接
 → 事务：写入 entity_history（当前 state + 当前 version）
         → 按 N 修剪最旧行
         → 应用 value 到 state / group / resource_id
         → version += 1; revision += 1
 → 释放锁，广播 unlocked
 → 提交者：applied{ref, revision, version}
 → 其他人：update{entity_id, revision, version, data_path, value, author}
```

- `value` 对叶子字段是标量；对容器是**整个新容器值**（数组/对象整体替换）。
- `resource_id` patch 先做项目内唯一性校验与命名空间前缀校验；`group` patch 校验格式。
- 不携带 `base_version`：字段锁已保证该路径无并发写入；所有可写路径都要求先 lock。

### 6.6 create / delete / rollback

- `create`：校验 kind/ui_kind 映射、state、resource_id 完整字符串唯一性（§3.4）→ `revision=1, version=1` → 存实体 → 应答 `created`；房间广播 `created`（他人直接加入本地集合）。不写 entity_history（无旧状态）。
- `delete`：校验无他人锁 → **物理删除** entities 行（entity_history 级联清除）→ 应答并广播 `deleted {entity_id}`；客户端立即移除，无 tombstone。
- `rollback`：校验无他人锁 → 取 `version-1` 快照（不存在 → `error HISTORY_EMPTY`）→ 应用 state、删除该快照行 → `version-=1; revision+=1` → 应答并广播 `rolled_back`（全量 state）。

### 6.7 错误码（error.code）

```
BAD_JSON / UNAUTHORIZED / PROJECT_NOT_FOUND / ENTITY_NOT_FOUND
VALIDATION / RESOURCE_CONFLICT / STALE_LOCK / LOCK_DENIED /
ENTITY_LOCKED / HISTORY_EMPTY / RATE_LIMITED（预留）
```

REST 额外错误码：`FILE_NOT_FOUND`（404）、`FILE_TOO_LARGE`（413）。

---

## 7. REST API（v2 增量）

保持 v1 §5 已定部分，改动如下：

```text
# 不变：auth、admin（M1.1 已实现）
# 项目（M1.2）：
GET    /api/projects                 POST /api/projects {module_id, display_name}
GET    /api/projects/:id             PATCH /api/projects/:id

# 文件系统（M2，新增）：
POST   /api/files                    GET /api/files/:file_id      DELETE /api/files/:file_id

# 移除/暂缓：
# /api/projects/:id/export           → 延后（导出不在 v2 范围）
# 实体 REST 端点                      → 不做，实体操作全部走 WS
```

---

## 8. 前端结构（apps/web）

```
/              项目列表（M1.2）
/projects/:id  编辑器主界面（M2）
```

### 8.1 状态（Pinia）

| store | 内容 |
| --- | --- |
| `auth` / `theme` | 已有，不动 |
| `projects` | 项目列表 + 当前项目元数据 |
| `entities` | `Map<entity_id, EntityRecord>` + `Map<entity_id, revision>` 向量 |
| `ui` 或 `editor` | 选中 entity / data_path / 表单草稿 |
| `sync` | WS 状态机（connecting → joined → reconnecting）、消息路由、心跳、rejoin |
| `locks` | 本地持有锁、他人锁视图（locked/unlocked/lock_denied 驱动） |
| `presence` | 在线成员 + 各自当前位置（presence 驱动） |

### 8.2 编辑器界面（v2 调整）

- 左侧实体树：第一层 **group**，第二层按 `REGISTRY_OF_KIND` 分组，叶子为实体；删除/新建实体入口。
- 中间：按 `ui_kind` 查组件注册表渲染：
  - `dag-node` / `progress-dag` / `file-tree` / `script` / `code` / `asset` / `form`
  - 未知 ui_kind 回退 `form` + JSON 只读预览。
- 右侧：历史面板（`history` 读取 + `rollback` 按钮）、文件上传/下载/手动删除。
- 底部：连接状态、在线成员与 focus 位置、锁提示（“user 正在编辑 state:/display/label”）。

### 8.3 字段编辑交互（锁流程）

```
focus 字段
 → lock(data_path)
   ├─ locked → 本地可编辑（输入框解除禁用）
   └─ lock_denied → 显示持有者，保持只读
编辑（叶子即时/防抖提交；代码内容 500ms 整文提交；容器提交整个新值）
 → patch{data_path, value}
   ├─ applied → 更新 revision/version，锁已自动释放
   └─ STALE_LOCK → 重新 lock 后再提交
失焦/取消 → unlock
```

- 每连接一把锁的 UX 约束：切换编辑目标字段时，旧字段必须已提交或显式放弃；提交失败后重新加锁。
- 文本资产：见 §4.4（下载 → 编辑 → 上传新 file_id → patch 引用）。
- 创建表单：前端按 kind 自动选中 ui_kind（显式发送）、自动补 resource_id 命名空间前缀（用户只填 id 部分）。

---

## 9. 配置与环境（server）

`.env` 新增：

```text
FILE_DATA_DIR=data/files            # 文件数据目录
MAX_FILE_BYTES=52428800             # 单文件上限，默认 50 MiB
ENTITY_HISTORY_LIMIT=20             # 每实体历史快照上限 N（建库时固化进 app_meta）
```

`ServerConfig` 同步扩展；`ENTITY_HISTORY_LIMIT` 校验为 ≥1 整数。

---

## 10. 里程碑与验收（v2 修订）

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| M0 | 仓库骨架 | ✅ 完成 |
| M1.1 | 用户管理 + 认证界面 | ✅ 完成（已归档） |
| M1.2 | 项目 CRUD（后端 projects 表 + 前端项目列表） | 待实施 |
| M2 | migration v3（entities/entity_history/files/app_meta）、WS 协议 v2（认证房间、锁、focus、create/patch/delete/rollback/history、重连全量）、文件系统端点、编辑器主界面（group 树 / ui_kind 组件 / 锁与在场 / 历史面板） | 待提案 |
| 未来 | Python 包生成与 zip 导出（原 M3，延后） | 不在本版验收 |

### M2 验收标准

- 双浏览器同一字段：后到者 `lock_denied` 并看到持有者；持有者提交后另一方可立即加锁。
- 断线/关闭标签页：对应连接锁与 focus 被清理，其他用户可加锁。
- 重连：只同步 revision 不一致的实体全量状态；被物理删除的实体进入 `removed_ids`，客户端集合与服务端一致。
- 回退：version -1 应用成功、version 递减但 revision 递增，其他客户端收到 `rolled_back` 且不丢弃。
- 历史：更新 N 次后最旧快照被修剪；回退消耗快照且不可 redo；删除实体时历史级联清除。
- 文件：上传下载 sha256 一致、元数据入库；asset 引用更新走锁；重启后文件仍在；手动删除无条件生效且磁盘与 files 表同时清空，允许实体中存在悬空 file_id。
- 删除重建：删除实体后可用相同 `resource_id` 重新创建。
- 服务重启：锁清空、客户端重连重锁；app_meta 中的 N 不受 .env 修改影响。
- `pnpm type-check`、`pnpm build`、`pnpm --dir apps/server test` 全绿。

---

## 11. 对现有代码的影响（实施时，非本轮）

| 位置 | 变更 |
| --- | --- |
| `packages/puzzle-schema/src/types.ts` | `Entity` 改为 v2 元数据（无 deleted/resource_namespace）+ 双计数器；`FileTreeNodeState`/`ProgressNodeState` 仅存节点数据、新增 `FileTreeState`/`ProgressDagState`；`AssetState` 合并为 `{file_id, media_type}`；`UI_KINDS`（含 `file-tree`/`progress-dag`）、命名空间前缀目录与映射 |
| `packages/puzzle-schema/src/sync.ts` | 协议 v2 消息全集（§6），`SYNC_PROTOCOL_VERSION=2` |
| `packages/puzzle-schema/src/validate.ts` | `isValidGroup`、resource_id 解析/校验、data_path 解析 |
| `apps/server/src/db/migrations.ts` | v2：projects（M1.2）；v3：entities/entity_history/files/app_meta |
| `apps/server/src/ws/hub.ts` | 替换 echo：会话认证、项目房间、消息分派、锁/focus Map |
| `apps/server/src/` | 新增 `services/entities.ts`、`services/files.ts`、`routes/files.ts` |
| `apps/web/src/` | 新增 `sync/`、`stores/{entities,locks,presence}.ts`、`components/ui/` 组件注册表、编辑器视图 |

实施前按 OpenSpec 流程另立 change（建议先 M1.2，再 M2），本文档转为 proposal/design 的输入。

---

## 12. 待审阅默认项（草案中采用的默认值）

1. `resource_id` 唯一性作用于完整字符串（含命名空间前缀），不同命名空间的 id 部分可重复；同一命名空间内唯一，`stable-id` 命名空间跨 6 类 kind（§3.1/§3.4）。
2. `ui_kind` 六值目录与 kind 映射（§3.3）；创建必填、服务端校验。
3. `group` 默认 `main`、单段 Python 模块名（§3.5）。
4. data_path 中 `group`/`resource_id` 的 json_path 为空（`...@group:` 形式）（§5.1）。
5. 删除即物理删除并级联清除历史（§3.8/§6.6）。
6. 锁无 TTL，仅靠提交/失焦/unlock/断线释放（§5.4）。
7. 文件数据不可变；无自动 GC；手动删除无条件生效、接受悬空引用（§4.3/§4.5）。
8. 文本资产的并发编辑：谁最后 patch `file_id` 谁生效，无额外冲突提示（§4.4）。
9. `ENTITY_HISTORY_LIMIT` 默认 20。
10. 心跳 30s / 服务端 90s 超时（§6.1）。
11. 文件元数据仅存 `original_name/media_type/size/sha256/uploaded_by/created_at`，不提供元数据编辑与列表端点（§4.2）。
12. `file-tree` 与 `progress-dag` 约定每个项目各一个（resource_id 建议 `file-tree:main` / `progress-dag:main`），但服务端不强制检查数量；节点与拓扑分离（§3.3/§3.6）。
13. file-reference 与 asset 已合并：`asset.state = {source_reference?, file_reference?, media_type}`，命名空间为 `asset`；多个 asset 可共享同一 `file_reference`（§3.4/§3.6/§4.1）。

---

## 附录：对 14 点讨论与后续修订的落实

| # | 原始要点 | 本文档位置 |
| --- | --- | --- |
| 1 | Project + 多 Entity | §2/§3.1 |
| 2 | 通用 entities + JSON，kind 后端用，ui_kind 前端用 | §3.1–3.3 |
| 3 | entity_group 分组 | §3.5 |
| 4 | resource_id 唯一，命名空间内嵌 | §3.4 |
| 5 | data_path 锁 + 内存 Map + 断线清理 | §5 |
| 6 | 分段 data_path 在场记录 | §5.5 |
| 7 | 全部同步操作走 WS | §6 |
| 8 | N 个旧版本快照表，revision/version 双计数 | §3.7–3.9 |
| 9 | 单实体手动回退、不可逆 | §3.7/§6.6 |
| 10 | 项目级增删历史 | 已确认第一版不做（§1.2） |
| 11 | N 配置 + 建库固定 | §3.9/§9 |
| 12 | blob 独立系统，UUID→bytes 落盘 | §4 |
| 13 | 重连全量、在线增量 | §6.4–6.5 |
| 14 | 暂不生成 Python 包，字段覆盖即可 | §1.3/§10 |
| 修订 1 | 实体删除即物理移除 | §3.1/§3.8/§6.6 |
| 修订 2 | resource_id 自带 `<namespace>:<id>` | §3.4 |
| 修订 3 | create 必须携带 ui_kind | §3.3/§6.2 |
| 修订 4 | data_path 改为 `<entity_id>@<root>:<json_path>` | §5.1 |
| 修订 5 | 文件元数据入 SQL + 手动删除端点，无 GC | §4 |
| 修订 6 | file-reference 与 asset 合并：asset.state={source_reference?, file_reference?, media_type}，命名空间为 asset；手动删除不检查悬空引用 | §3.2–3.6/§4 |
| 修订 7 | 新增 `file-tree`/`progress-dag` 容器 kind；节点实体去拓扑化 | §3.2–3.6 |
