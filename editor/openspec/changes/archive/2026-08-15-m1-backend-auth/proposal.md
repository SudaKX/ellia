# Proposal: m1-backend-auth

## Why

M1 的第一批功能全部依赖身份认证与用户数据：没有 SQLite 用户表和会话机制，项目 CRUD、WS 同步、前端登录页都无法开始。本 change 先把“用户管理”这一最底层、可独立验收的切片做完。

## What Changes

- `apps/server` 接入 `better-sqlite3`，新增数据库连接、建表与初始 admin 播种模块。
- 新建 `users`、`invite_codes`、`sessions` 三张表（`projects` 等表留给 M1.2）。
- 新增认证 API：
  - `POST /api/auth/register`：用户名 + 密码 + 一次性邀请码注册，成功后建立会话。
  - `POST /api/auth/login`、`POST /api/auth/logout`、`GET /api/auth/me`。
- 新增 admin API：
  - `POST /api/admin/invites`：生成带有效期的一次性邀请码。
  - `GET /api/admin/invites`：邀请码列表（含 used/unused/expired 状态）。
  - `DELETE /api/admin/invites/:code`：作废邀请码。
  - `GET /api/admin/users`：用户列表（前端提权面板需要，对 plan-v1 §5 的最小补全）。
  - `POST /api/admin/users/:id/promote`：将 user 提权为 admin。
- 新增 `requireAuth` / `requireAdmin` 中间件与统一 JSON 错误格式。
- 密码使用 Node 内置 `crypto.scrypt` 加盐哈希；会话为服务端 session 表 + HttpOnly cookie。
- 配置扩展：`DATABASE_PATH`、`SESSION_TTL_DAYS`，并写入 `apps/server/.env.example`。

## Capabilities

### New Capabilities

- `user-management`: 用户注册（一次性邀请码）、登录/登出/me、服务端会话、初始 admin 播种、admin 邀请码管理、用户列表与提权。

### Modified Capabilities

<!-- 无既有 capability；本项目 openspec/specs 为空。 -->

## Impact

- **代码**：`apps/server/src`（新增 `db/`、`auth/`、`routes/` 实现；扩展 `config.ts`、`app.ts`、`index.ts`）。
- **依赖**：新增 `better-sqlite3`、`@types/better-sqlite3`；`pnpm-workspace.yaml` 的 `allowBuilds` 增加 `better-sqlite3: true`。
- **运行时**：首次启动创建 `data/ellia.db`（已在 .gitignore 忽略）；启动顺序变为“DB 初始化 → admin 播种 → HTTP/WS 监听”。
- **API**：新增上述 9 个 REST 端点；对 M0 的 `/api/health` 与 WS echo 无破坏。
- **消费方**：`m1-frontend-auth` 依赖本 change 的 API 契约（cookie 会话 + 错误格式）。
