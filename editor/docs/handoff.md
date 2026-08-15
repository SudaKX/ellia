# 交接文档 — Ellia 谜题在线多人编辑器（editor/）

> 用途：新对话的起点。新会话开场时**先读本文档，再读 `docs/plan-v1.md`**，即可完整接管。
> 更新日期：本文档记录截至“v1 方案定稿”的全部调研结论、已确认决策与待办。

## 1. 项目背景与目标

在 `editor/`（`D:\Ds_Projects\FullStack\ellia\editor`）中创建一个**专属的在线多人编辑器**，用于编辑 Mythos 谜题模块，并支持将数据导出为合法的谜题模块（可放入 mythos 的 `puzzles/` 插件目录使用）。

- **上游后端**：`D:\Ds_Projects\FullStack\ellia\mythos`（Python 3.13+ / FastAPI）。
- **技术栈（已定）**：Vue3 + Vite 前端；Node.js Express 5 + 原生 `ws` 后端（TypeScript）；前端与后端通过 **pnpm workspace 共享 TS 包**共享数据结构定义。
- **协作模型（已定）**：后端持有编辑对象的权威状态，状态同步（增量 + 全量），**不使用 CRDT**。
- **导出（已定）**：打包导出 zip（完整模块目录 + 合并版 `puzzles/__init__.py`），导出前**不做校验**。
- **v1 方案文档**：`editor/docs/plan-v1.md`（完整方案，含数据模型、同步协议、REST API、导出生成器、里程碑）。

## 2. Mythos 后端调研结论（已完成的功课，勿重复调研）

### 2.1 谜题模块的合法形态

- 模块 = `mythos/puzzles/<module_id>/` 插件目录，含：
  - `__init__.py`：导出 `register(registries)` 函数，向各 Registry 声明数据 + 注册 Python 回调；
  - `assets/**`：静态文件；
  - `assets/file-tree.json`：静态文件树 manifest（`schema_version: 1`，含 `module`、树结构、`stable_id`/`display`/`access_rule`/`source{relative_path,media_type}`/`download_name`）。
- `mythos/puzzles/__init__.py` 的 `register_all()` **显式 import 并调用**各模块的 `register()`，新模块需要在此登记（导出时处理，见 §4）。
- 硬约束（编辑器表单/导出必须遵守）：
  - 模块只能向既有 Registry 注册内容与回调，**不能新增 HTTP Router、不持有 Session**；
  - `module_id` 必须是单一路径段；`stable_id` 全项目唯一（静态节点与 Artifact 节点不得冲突）；
  - Hint 引用的 `credit_id` 必须已注册；`validation_id` 为 slug 格式；
  - 所有回调必须经 `module_handler(MODULE_ID)(revision)` 装饰器注册（callback ID 参与 mythos 版本计算）。

### 2.2 11 个数据注册表（RegistryBundle）

| # | Registry | 注册数据模型 | 用途 |
| --- | --- | --- | --- |
| 1 | `files` | `FileReference`、`StaticNodeSpec`、`file-tree.json` manifest | 静态文件树（启动时物化到对象存储） |
| 2 | `progress` | `NormalProgressNode`/`BranchProgressNode`/`MergeProgressNode` | 谜题进度 DAG（entry/checkpoint/边） |
| 3 | `scripts` | `Script(stable_id, revision, body, access_rule)` | 终端交互脚本 |
| 4 | `validations` | `ValidationAttempt(stable_id, validation_id, handler)` | 答案验证 |
| 5 | `artifacts` | `ArtifactTemplate(generator)`、`ArtifactNodeTemplate(node_generator)` | 玩家专属动态文件 |
| 6 | `accounts` | `VirtualAccountTemplate(account_id, display_name, permission, metadata)` | 虚拟账号模板 |
| 7 | `credits` | `CreditTemplate(credit_id, display_name, metadata)` | 货币类型（VTB 内置） |
| 8 | `hints` | `Hint(stable_id, source, download_name, display, credit_id, credit_amount, access_rule)` | 提示 |
| 9 | `events` | Event listener（`PlayerConstructedEvent` 等） | 进程内事件总线 |
| 10 | `tasks` | 惰性任务定义 | 周期性奖励/状态 |
| 11 | `achievements` | `AchievementDefinition`（predicate + reward 回调） | 成就 |

### 2.3 关键参考文件（实现导出/类型时查阅）

- `mythos/src/mythos/registry/bundle.py` — RegistryBundle 与 freeze 顺序
- `mythos/src/mythos/registry/<domain>/definitions.py`、`registry.py` — 各注册表字段定义
- `mythos/puzzles/example/__init__.py` — 唯一完整模块示例（回调写法范本）
- `mythos/puzzles/example/assets/file-tree.json` — manifest 范本
- `mythos/puzzles/__init__.py` — `register_all` 范本
- `mythos/docs/architecture/startup-registration-and-artifact-flow.md` — 注册/物化/freeze 全流程与版本体系
- `mythos/docs/modules/example.md` — Example 模块注册项总表
- `mythos/docs/README.md` — 文档索引

## 3. 已确认的 v1 决策（四轮问答结论，均不可擅自更改）

| 主题 | 决策 |
| --- | --- |
| 编辑范围 | 覆盖全部 11 个注册表；Python 回调允许用户直接写代码（非 DSL） |
| 协作模式 | 实时协同；后端权威状态；状态同步（增量 + 全量）；不用 CRDT |
| 同步粒度 | **实体级版本号 + LWW**；Python 代码块为独立实体（与宿主条目一一绑定） |
| 冲突策略 | patch 无论 base_version 是否过期都按接收顺序应用（LWW），过期时提示提交者 |
| 版本号作用 | 增量锚点 / LWW 与乱序防护 / 断线恢复 diff 基准 / 幂等 / 一致性，是协议骨干 |
| 持久化 | SQLite（better-sqlite3） |
| 历史存储 | 持久化每实体补丁日志 `entity_patches`（`{field:{from,to}}` 双向值，上限 100 条）；内存环形缓冲做热路径；三级回退（内存→DB 日志→实体全量）；回滚 = 生成新版本，不破坏历史 |
| 认证 | 仅 user/admin 两角色；注册必须填一次性邀请码（带有效期）；首次启动由 `.env` 播种初始 admin；admin 生成/作废邀请码、可提权 user |
| 项目权限 | 全局两层：所有登录 user 可见并编辑所有项目，无项目级成员隔离 |
| 代码编辑 | **CodeMirror 6 + `@codemirror/lang-python`**（仅语法高亮，无语法检查、无 lint；不用 Monaco）；声明数据用结构化表单 |
| 进度图编辑 | 列表/表格编辑节点与边 + 本地 DAG 可视化渲染预览（只读） |
| 资产文件 | 文本文件直接编辑 + 非文本二进制上传，均入项目资产库 |
| 导出校验 | **不校验**（只打包，正确性由 mythos 侧验证） |
| 导出产物 | zip：完整 `puzzles/<module_id>/` 目录 + 合并版 `puzzles/__init__.py` + `README.txt` 部署说明 |
| 共享类型 | pnpm workspace 共享 TS 包，路径在 editor 内（`packages/puzzle-schema`，包名 `@ellia/puzzle-schema`） |
| 目录布局 | `apps/*` 分层：`apps/web`（现有 Vue 脚手架移入）+ `apps/server` + `packages/puzzle-schema` |
| 预览/试玩 | v1 不做谜题运行预览 |
| 服务端技术 | TypeScript + Express 5 + 原生 ws（不用 socket.io） |

### 待确认/实现时注意的小设计（方案中已给定默认值，用户未明确反对）

- **deploy_baseline**：合并版 `puzzles/__init__.py` 的生成需要基线——方案默认“用户在项目配置中粘贴一次当前 mythos 的 `puzzles/__init__.py` 内容，导出时幂等合并本模块；未配置基线则降级为模块目录 + `register_all.patch` 片段”。实现前可与用户再确认。
- 表单内保留轻量字段格式即时提示（编辑体验），但**不是**导出强校验，与“导出不校验”不冲突。

## 4. v1 方案要点速览（详见 plan-v1.md）

- **仓库**：editor 根为 pnpm workspace（`pnpm-workspace.yaml`: `apps/*`, `packages/*`）；现有 `src/`、`index.html`、`vite.config.*` 移入 `apps/web/`。
- **共享包** `@ellia/puzzle-schema`：`types.ts`（15 种实体 kind + 11 注册表声明类型）、`validate.ts`（编辑期轻校验）、`python.ts`（Python 代码块 slot 与签名模板）、`exporter/`（file-tree.json / `__init__.py` 模板 / `puzzles/__init__.py` 合并 / zip 打包）。
- **实体种类**（同步与版本的基本单位）：`progress-node`、`file-tree-node`、`asset`、`hint`、`script`、`validation`、`artifact-template`、`artifact-node`、`account-template`、`credit-template`、`achievement`、`task`、`event-listener`、`python-block`（另有自由辅助函数）。
- **SQLite 表**：`users`、`invite_codes`、`projects`（含 `deploy_baseline`）、`entities`（id/kind/version/state JSON/deleted）、`entity_blobs`、`entity_patches`、`sessions`。
- **WS 协议**：`join{project_id, vector}` → `sync{entities, tombstones}`；`patch{entity_id, base_version, changes}` → `applied` + 广播 `update{..., base_mismatch?}`；`ping/pong`、`presence`。文本编辑防抖约 500ms 整文提交。
- **REST**：auth（register/login/logout/me）、admin（invites 生成/列表/作废、promote）、projects（CRUD + `/export`）、WS `/ws/projects/:id`。
- **导出模板要点**：自动生成 imports、`MODULE_ID`、`_handler = module_handler(MODULE_ID)`、用户函数体 + 自动补 `@_handler` 装饰器、`register()` 内固定顺序的注册调用、`access_rules` 名→函数映射、`register_json_tree_asset(...)`。
- **前端**：`/login`、`/register`、`/`（项目列表）、`/admin`、`/projects/:id`（左实体树 / 中表单+CodeMirror+DAG 预览 / 右导出+历史 / 底部连接与成员状态）。
- **里程碑**：M0 骨架 → M1 认证与项目 → M2 数据模型与同步 → M3 导出；验收项见 plan-v1.md §9。

## 5. 当前仓库状态

- **M0 仓库骨架已完成**：
  - pnpm workspace（`pnpm-workspace.yaml`: `apps/*`, `packages/*`）；根聚合脚本 `pnpm dev`（并行 web+server）/ `pnpm type-check` / `pnpm build`。
  - Vue 脚手架已迁入 `apps/web/`（`@` 别名指向 `apps/web/src`；dev 代理 `/api`、`/ws` → `http://localhost:3000`，可用 `VITE_API_PROXY_TARGET` 覆盖）。
  - `apps/server/`（`@ellia/server`，Express 5 + 原生 ws，tsx 运行）：`src/{index,app,config}.ts`、`src/ws/hub.ts`（M0 WS echo：hello/ping→pong/echo）、`.env.example`（PORT、ADMIN_USERNAME、ADMIN_PASSWORD）；`src/{routes,db,export,auth}/` 空目录待 M1+。
  - `packages/puzzle-schema/`（`@ellia/puzzle-schema`，源码直出 exports）：`types.ts`（14 种实体 kind + 11 注册表 + KindStateMap + Change/EntityPatch/Project）、`sync.ts`（WS 协议消息）、`python.ts`（9 种 slot 签名模板）、`validate.ts`（module_id/stable_id/validation_id 轻校验）、`exporter/`（M3 占位）。
- 已产出文档：`editor/docs/plan-v1.md`（方案）、`editor/docs/handoff.md`（本文档）。
- **M0 已复核通过**：`pnpm install --frozen-lockfile`、`pnpm type-check`、`pnpm build` 全部通过；`pnpm dev` 冒烟（web 200、`/api` 代理、`/ws` ping/pong 与 echo）通过。
- **尚未开始实现**：M1 认证与项目（SQLite、注册/登录/邀请码/初始 admin、项目 CRUD）；M2 数据模型与同步；M3 导出。

## 6. 环境事实与坑（新会话务必注意）

- 会话工作目录：`D:\Ds_Projects\FullStack\ellia\editor`。上游 mythos：`D:\Ds_Projects\FullStack\ellia\mythos`。
- 仓库边界见根 `AGENTS.md`：mythos 只用 `mythos/.venv`；desktop/ 与本项目无关；提交遵循 `type(module): description`（小写）。
- **工具沙箱问题（已解决）**：当前会话文件策略为 danger-full-access，`pwsh` 可正常执行（pnpm 11.5.1 / node v24.16.0 已验证）。若后续会话出现 `SetNamedSecurityInfoW failed`，先检查会话文件策略。
- **pnpm 11 配置位置（重要）**：`package.json` 里的 `pnpm.onlyBuiltDependencies` 已被 pnpm 11.5 忽略；构建脚本白名单必须写在 `pnpm-workspace.yaml` 的 `allowBuilds`（当前为 `esbuild: true`）。写回 package.json 会导致 `ERR_PNPM_IGNORED_BUILDS` 并阻断所有 `pnpm <script>`。
  - `glob`/`grep` 在 mythos 根目录会因 `.pytest_cache` 拒绝访问而失败；应使用 `src/**`、`puzzles/**` 等子目录锚定路径。
  - `read`/`write`/`edit` 工具工作正常。
- 本仓库是 pnpm 项目；AGENTS.md 中 desktop 的 pnpm 命令形式（`pnpm --dir ...`）可参考，但 editor 改为 workspace 后按根目录执行。
- 用户沟通偏好：中文；喜欢“多轮提问逐步确认”；对架构问题会追问原理（回答时把“为什么”讲清楚）。

## 7. 新对话开场建议

```text
请先阅读 editor/docs/handoff.md 与 editor/docs/plan-v1.md，
M0 已完成，从 M1（SQLite 初始化、注册/登录/邀请码/初始 admin、项目 CRUD）开始实现。
```

M1 的具体步骤：① `apps/server` 接入 better-sqlite3，按 plan-v1.md §3.3 建表（users / invite_codes / projects / entities / entity_blobs / entity_patches / sessions）；② 实现 `/api/auth/*`（注册必须一次性有效邀请码、登录/登出/me，初始 admin 从 `.env` 播种）；③ 实现 `/api/admin/*`（邀请码生成/列表/作废、用户提权）；④ 实现 `/api/projects` CRUD（module_id 唯一校验，用 `@ellia/puzzle-schema` 的 `isValidModuleId`）；⑤ `apps/web` 落地 `/login`、`/register`、`/`（项目列表）、`/admin` 路由与 Pinia auth 状态。
