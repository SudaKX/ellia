# M1 拆分计划 — 认证与项目

> 状态：拆分定稿（M1 启动前）。依据：`docs/plan-v1.md` §3.3/§5/§7/§8、`docs/handoff.md` §7。
> 原则：**纵向切片**，每个切片都有可访问、可验证的成果；**后端先行**，前端紧随配套联调。

## 1. M1 总目标（回顾）

- SQLite（better-sqlite3）初始化；
- 注册 / 登录 / 登出 / me 认证 API；
- 一次性邀请码（带有效期）与初始 admin 播种；
- admin 邀请码管理与用户提权；
- 项目 CRUD（module_id 唯一校验）；
- 前端 `/login`、`/register`、`/`（项目列表）、`/admin` 路由与 Pinia auth 状态。

## 2. 切片总览

| 切片 | Change | 范围 | 可验证成果 |
| --- | --- | --- | --- |
| **M1.1a 后端用户管理（先做）** | `m1-backend-auth` | better-sqlite3 接入；`users`/`invite_codes`/`sessions` 表；auth API；admin 邀请码/提权 API；初始 admin 播种 | curl / 浏览器可完成注册→登录→admin 管理全流程 |
| **M1.1b 前端认证界面（配套）** | `m1-frontend-auth` | Pinia auth store、API client、`/login`、`/register`、`/admin`、路由守卫、根页面占位 | 浏览器可视化完成注册/登录/邀请码管理/提权 |
| M1.2a 后端项目 CRUD | `m1-backend-projects`（后续提出） | `projects` 表 + CRUD + `isValidModuleId` 唯一校验 + auth 中间件复用 | curl 可创建/列出/编辑项目 |
| M1.2b 前端项目列表 | `m1-frontend-projects`（后续提出） | `/` 项目列表、新建项目表单、跳转编辑器占位 | 浏览器管理项目 |

## 3. 为什么先做“后端 SQLite 用户管理”

1. **认证是一切 API 的前置**：项目 CRUD、WS 同步都要挂在 `requireAuth` 之后，没有用户/会话就没有上层功能。
2. **DB 是所有持久化的地基**：先固定连接、迁移、种子数据的模式，M1.2 只追加表即可。
3. **邀请码/admin 闭环可独立验收**：注册、登录、生成邀请码、提权构成完整业务闭环，不依赖项目功能。
4. **前端立即配套**：否则后端做完只能 curl 验证；“可访问界面”让切片对用户可见、可反馈。

## 4. M1.1 切片边界

### 4.1 后端（m1-backend-auth）

- 依赖新增：`better-sqlite3`（已确认决策）、`@types/better-sqlite3`；`pnpm-workspace.yaml` 的 `allowBuilds` 增加 `better-sqlite3: true`。
- 建表（本切片）：`users`、`invite_codes`、`sessions`；`projects`/`entities` 等留到 M1.2。
- 密码：Node 内置 `crypto.scrypt`（随机盐 + `timingSafeEqual`），不引入 bcrypt 原生依赖。
- 会话：服务端 session 表 + HttpOnly `SameSite=Lax` cookie（REST 与后续 WS 握手自动携带，避免 token 暴露给 JS）。
- 初始 admin：启动时若不存在 admin，用 `.env` 的 `ADMIN_USERNAME`/`ADMIN_PASSWORD` 播种；默认密码启动时打警告日志。
- 中间件：`requireAuth`、`requireAdmin`；统一 JSON 错误 `{ error: { code, message } }`。
- 端点（详见两个 change 的 specs）：

```text
POST   /api/auth/register      {username, password, invite_code}   → set-cookie + user
POST   /api/auth/login         {username, password}                → set-cookie + user
POST   /api/auth/logout                                            → clear-cookie 204
GET    /api/auth/me                                                → user | 401
POST   /api/admin/invites      {expires_in_seconds}                → {code, expires_at}
GET    /api/admin/invites                                          → 邀请码列表（含状态）
DELETE /api/admin/invites/:code                                    → 204（作废）
GET    /api/admin/users                                            → 用户列表（前端提权面板需要）
POST   /api/admin/users/:id/promote                                → 提权为 admin
```

> 与 plan-v1 §5 的唯一增量：新增 `GET /api/admin/users`。原方案只有 promote 端点，但前端提权面板必须先列出用户；这属于补全 UI 所需的最小契约，不改动任何已确认决策。

### 4.2 前端（m1-frontend-auth）

- 路由：`/login`、`/register`、`/`（项目列表占位）、`/admin`。
- 状态：Pinia `auth` store（`user` / `initialized` / `fetchMe` / `login` / `register` / `logout`）。
- 守卫：未登录访问 `/`、`/admin` → `/login`；已登录访问 `/login`、`/register` → `/`；非 admin 访问 `/admin` → `/`。
- 界面：语义化表单 + 错误提示；`/admin` 分“邀请码管理”（生成/复制/作废/状态列表）与“用户管理”（列表 + 提权）。
- 联调：复用 M0 的 Vite 代理，`credentials: 'include'` 走 cookie 会话。

## 5. M1.1 验收标准（两端共享）

- 无 `.env` 播种信息时首次启动：admin 自动创建并打印安全警告。
- 未带 cookie 访问 `/api/auth/me` → 401；登录/注册后 → 200 + user。
- 注册必须使用未过期、未使用的邀请码；同一邀请码第二次注册 → 400。
- 只有 admin 能生成/列出/作废邀请码、查看用户列表、提权；user 访问 → 403。
- 浏览器完成：登录页 → admin 面板 → 生成邀请码 → 新窗口注册 → 新 user 登录 → admin 提权 → 新 user 刷新变为 admin。
- `pnpm type-check` 与 `pnpm build` 保持通过。

## 6. 后续切片预览（本文件保存，暂不提出 change）

- M1.2a 后端：`projects` 表；`GET/POST /api/projects`、`GET/PATCH /api/projects/:id`；创建时用 `@ellia/puzzle-schema` 的 `isValidModuleId` + 全库唯一校验。
- M1.2b 前端：`/` 项目列表与新建表单；复用 auth store 与守卫；成功后进入编辑器占位页 `/projects/:id`。

## 7. 文件落点

- 本计划：`docs/m1-plan.md`
- 后端 change：`openspec/changes/m1-backend-auth/{proposal,design,tasks}.md`、`specs/user-management/spec.md`
- 前端 change：`openspec/changes/m1-frontend-auth/{proposal,design,tasks}.md`、`specs/auth-web/spec.md`
