# Ellia 谜题在线多人编辑器 — v1 方案

> 状态：方案定稿（第 4 轮问答后）。目标仓库：`editor/`（本目录）。上游依据：`mythos/docs/**`、`mythos/src/mythos/registry/**`、`mythos/puzzles/example/**`。

## 1. 目标与非目标

### 目标

- 专属在线多人编辑器：多人通过状态同步（增量 + 全量）协作编辑谜题模块，后端（Express）持有编辑对象的权威状态。
- 覆盖 Mythos 全部 11 个注册表；Python 回调（access_rule / generator / handler / listener 等）由用户直接在编辑器中编写 Python 代码。
- 一键导出为合法谜题模块 zip：完整 `puzzles/<module_id>/` 目录 + 合并版 `puzzles/__init__.py`。
- Vue3 前端与 Express 后端共享数据结构定义（共享 TS 包）。

### 非目标（v1 不做）

- 导出前校验（Python 语法/运行期干跑）：只打包，正确性由使用方在 mythos 侧验证。
- CRDT / 字符级实时协同、光标共享（仅做在线成员列表）。
- 谜题运行预览/试玩。
- 项目级成员隔离（见 §7）。

## 2. 仓库布局（pnpm workspace）

```
editor/
├── pnpm-workspace.yaml          # packages: ["apps/*", "packages/*"]
├── package.json                 # workspace 根：聚合 dev/build 脚本
├── docs/
│   └── plan-v1.md               # 本文档
├── apps/
│   ├── web/                     # Vue3 + Vite（现有脚手架移入）
│   │   └── src/                 #   views/ stores/ components/ sync/ schema-forms/
│   └── server/                  # Express 5 + ws（TypeScript）
│       └── src/                 #   routes/ ws/ db/ export/ auth/
└── packages/
    └── puzzle-schema/           # @ellia/puzzle-schema 共享包
        └── src/
            ├── types.ts         #   11 个注册表的声明数据 TS 类型 + 实体模型
            ├── validate.ts      #   编辑期表单校验（轻量，非导出强校验）
            ├── python.ts        #   Python 代码块模型（slot 种类、签名模板、名称规则）
            └── exporter/        #   导出生成器（纯函数）：file-tree.json / __init__.py / zip
```

- `@ellia/puzzle-schema` 被 `apps/web` 与 `apps/server` 共同 import，是数据结构的唯一事实源。
- 现有 `editor/src`、`index.html`、`vite.config.*` 等整体移入 `apps/web/`。

## 3. 数据模型（共享 TS 包 + SQLite）

### 3.1 实体划分（同步粒度）

每个项目由若干**实体**组成；实体是同步、版本号、补丁日志的基本单位。实体种类：

| 实体 kind | 对应注册表 | 声明字段（state JSON） | Python 引用 |
| --- | --- | --- | --- |
| `progress-node` | progress | `stable_id, node_kind(normal/branch/merge), successors[], is_entry, triggers_checkpoint` | — |
| `file-tree-node` | files | `stable_id, kind(directory/file), name, display{label,description,icon,sort_order}, hidden, download_name` | `access_rule` |
| `asset` | files/hints 源 | `path, media_type, text?`（文本）/ 二进制存 blob 表 | — |
| `hint` | hints | `stable_id, source(asset ref), download_name, display{title,teaser,icon,sort_order}, credit_id, credit_amount` | `access_rule` |
| `script` | scripts | `stable_id, revision, body{kind, lines[], input?, validation_id?}` | `access_rule` |
| `validation` | validations | `stable_id, validation_id` | `handler` |
| `artifact-template` | artifacts | `artifact_id, media_type, download_name` | `generator` |
| `artifact-node` | artifacts | `stable_id, path, artifact_locator, display, hidden, download_name` | `access_rule, node_generator` |
| `account-template` | accounts | `account_id, display_name, permission, metadata` | — |
| `credit-template` | credits | `credit_id, display_name, metadata`（VTB 为内置，不可编辑） | — |
| `achievement` | achievements | `achievement_id, secret, display{title,description}` | `predicate, reward` |
| `task` | tasks | `task_id, dependencies[]` | `handler` |
| `event-listener` | events | `event_type, priority, dependencies[]` | `listener` |
| `python-block` | （代码） | `name, slot, content` | — |

**Python 代码块是独立实体**：与宿主条目一对一绑定（如 `file-tree-node` 的 `access_rule` 引用一个 `python-block`），代码编辑与结构编辑互不覆盖。slot 决定签名模板（见 §3.2）。额外支持无宿主引用的自由辅助函数（导出时保留为模块级函数）。

### 3.2 Python 代码块 slot 与签名模板

编辑器提供签名模板（无语法检查，仅高亮 + 模板提示）：

```
access_rule:          def {name}(player: Player) -> bool
validation_handler:   async def {name}(context: ValidationContext, payload) -> ValidationResult
artifact_generator:   async def {name}(player: Player) -> RawArtifact
node_generator:       async def {name}(player, meta, node: ArtifactNode) -> ArtifactNode
achievement_predicate: def {name}(player: Player) -> bool
achievement_reward:   async def {name}(player: Player) -> None
task_handler:         async def {name}(context: TaskContext) -> None
event_listener:       async def {name}(context: EventContext) -> None
free:                 任意模块级函数
```

导出器负责添加 `@_handler(...)` 装饰器与 imports；用户只写函数体。

### 3.3 SQLite 表

```sql
users(id, username UNIQUE, password_hash, role('user'|'admin'), created_at)
invite_codes(code PK, created_by, expires_at, used_by, used_at)   -- 一次性
projects(id, module_id UNIQUE, display_name, description,
         deploy_baseline TEXT,        -- 当前 mythos puzzles/__init__.py 内容（导出合并用）
         created_by, created_at, updated_at)
entities(id, project_id, kind, ref, version INTEGER, state TEXT/*JSON*/,
         deleted INTEGER, updated_at)        -- version/state 即权威当前状态
entity_blobs(entity_id, data BLOB)           -- 二进制资产
entity_patches(id AUTOINC, entity_id, base_version, new_version,
         changes TEXT/*{field:{from,to}}*/, author_id, created_at)  -- 每实体上限 N=100
sessions(token PK, user_id, expires_at)      -- 可改为内存
```

## 4. 同步协议（ws，JSON 消息）

**模型**：后端权威状态；实体级版本号 + LWW；补丁双向存储。

### 消息

```text
C→S  join        {project_id, vector: {entity_id: version}}
S→C  sync        {entities: [{id, kind, version, state}], tombstones: [{id, version}]}
                  -- 服务器对 vector 不一致的实体发全量状态；客户端缺失的实体发全量
C→S  patch       {entity_id, base_version, changes: {field: {from, to}} | {field: value}}
S→C  applied     {ref, entity_id, version}                      -- 给提交者确认
S→C  update      {entity_id, version, changes, author, base_mismatch?}  -- 广播给其他人
C→S  ping / S→C pong
S→C  presence    {users: [{id, username}]}                      -- 在线成员列表
```

### 规则

- **LWW**：patch 无论 `base_version` 是否过期都按服务器接收顺序应用（字段覆盖），`base_mismatch=true` 时通过 `applied/update` 提示提交者“建立在旧版本上，可能覆盖他人改动”。
- **增量 + 全量三级回退**：内存环形缓冲（秒级重连）→ DB 补丁日志（窗口内重放，跨重启有效）→ 实体全量状态（始终可用）。补丁日志存 `{from,to}` 双向值，正向重放取 `to`，回滚反向取 `from`。
- **文本编辑**：CodeMirror 内容防抖（约 500ms）后作为 `{content: 全文}` patch 提交，不做字符级 diff。
- **回滚**：任一实体可查看版本历史（author/时间/变更），回滚 = 生成新版本（回滚也入日志，历史不破坏）。
- **删除**：tombstone（`deleted=1` + 版本 +1），不物理删除，保证版本向量比对正确。

## 5. REST API

```text
POST /api/auth/register {username,password,invite_code}   # 邀请码必须有效且未用
POST /api/auth/login / POST /api/auth/logout / GET /api/auth/me
# admin：
POST   /api/admin/invites {expires_in}   # 生成一次性邀请码
GET    /api/admin/invites                # 列表（含状态）
DELETE /api/admin/invites/:code          # 作废
POST   /api/admin/users/:id/promote      # 提权为 admin
# 项目（全局两层权限：登录 user 均可编辑所有项目；admin 额外管邀请码/用户）：
GET  /api/projects            POST /api/projects {module_id, display_name}
GET  /api/projects/:id        PATCH /api/projects/:id
POST /api/projects/:id/export # 生成并下载 zip
# WS：/ws/projects/:id （token 认证）
```

## 6. 导出生成器（@ellia/puzzle-schema/exporter）

纯函数：项目实体集合 → 文件内容集合 → zip 字节。产物：

```text
puzzles/<module_id>/__init__.py     # 由模板生成：imports、MODULE_ID、_handler、
                                    # python-block 函数体（自动加 @_handler 装饰器）、
                                    # register() 中按固定顺序调用各 Registry
puzzles/<module_id>/assets/**       # 全部资产（文本/二进制原样）
puzzles/<module_id>/assets/file-tree.json  # 由 file-tree-node 实体生成 manifest
puzzles/__init__.py                 # 合并版：项目 deploy_baseline + 本模块幂等合并
README.txt                          # 部署说明（放置位置、重启 mythos）
```

要点：

- `file-tree-node` 的 `access_rule` 引用 → `access_rules={名: 函数}` 映射 + manifest 中写规则名。
- 无 `deploy_baseline` 时降级：只导出模块目录 + `register_all.patch` 片段文件。
- 不做导出校验（与决策一致）；模块目录内不包含 mythos 框架代码。

## 7. 认证与权限

- 仅两角色 `user` / `admin`。**全局两层**：所有登录 user 可见并编辑所有项目；无项目级成员隔离。
- 首次启动：从 `.env`（如 `ADMIN_USERNAME`/`ADMIN_PASSWORD`）播种初始 admin。
- 注册必须填写**一次性邀请码**（带有效期）；邀请码仅 admin 可生成/作废；admin 可将 user 提权为 admin。

## 8. 前端结构（apps/web）

```text
/login  /register           # 注册含邀请码输入
/                          # 项目列表（新建项目：module_id 唯一校验）
/admin                     # 邀请码管理、用户提权（admin only）
/projects/:id              # 编辑器主界面
```

编辑器主界面布局：

- 左侧：实体树（按注册表分组：Progress / Files / Hints / Scripts / Validations / Artifacts / Accounts / Credits / Achievements / Tasks / Events / Python 代码块）
- 中间：结构化表单（声明数据）+ CodeMirror 6（`@codemirror/lang-python`，仅高亮）+ progress DAG 本地可视化预览（只读渲染）
- 右侧：导出面板（deploy_baseline 配置、导出按钮、zip 下载）+ 实体验证/历史（版本历史与回滚）
- 底部：连接状态、同步状态、在线成员列表

技术：Pinia（auth / projects / entities-by-id + versions / sync client）、vue-router、原生 `WebSocket` 客户端封装。

## 9. 里程碑

- **M0 仓库骨架**：workspace 建立、`apps/web` 迁移、`apps/server`（Express 5 + ws）可启动、`packages/puzzle-schema` 空包接通、WS echo 通。
- **M1 认证与项目**：SQLite 初始化、注册/登录/邀请码/初始 admin、项目 CRUD。
- **M2 数据模型与同步**：实体/补丁日志落库、WS 同步协议完整实现、编辑器主界面（树/表单/CodeMirror/DAG 预览/历史回滚）。
- **M3 导出**：file-tree.json、`__init__.py` 模板、`puzzles/__init__.py` 合并、zip 打包下载。
- **验收**：双浏览器并发编辑同一实体观察 LWW 与 `base_mismatch` 提示；断线重连后增量恢复；重启服务后版本向量仍能正确比对；导出的 zip 解压到 mythos `puzzles/` 后由使用方在 mythos 侧验证注册。

## 10. 待实现时注意

- `module_id` 必须是单一路径段；`stable_id` 全项目唯一；`validation_id` slug 格式；Hint 的 `credit_id` 必须已注册（编辑器表单做即时提示）。
- 生成的 `__init__.py` 中回调必须经过 `module_handler(MODULE_ID)` 装饰器（callback ID 参与 mythos 版本计算）。
- 开发期：`apps/web` 走 Vite dev server 代理到 `apps/server`；生产期 Express 静态托管 `apps/web/dist`。
