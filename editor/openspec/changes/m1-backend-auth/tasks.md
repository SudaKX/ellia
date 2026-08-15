# Tasks: m1-backend-auth

## 1. 依赖与配置

- [ ] 1.1 `apps/server` 添加 `better-sqlite3` 与 dev 依赖 `@types/better-sqlite3`，更新 lockfile
- [ ] 1.2 在 `pnpm-workspace.yaml` 的 `allowBuilds` 增加 `better-sqlite3: true` 并执行 `pnpm install`
- [ ] 1.3 扩展 `src/config.ts`：`DATABASE_PATH`（默认 `data/ellia.db`）、`SESSION_TTL_DAYS`（默认 30），同步更新 `.env.example`

## 2. 数据库骨架

- [ ] 2.1 实现 `src/db/database.ts`：打开连接、`PRAGMA journal_mode=WAL`、`foreign_keys=ON`、导出单例
- [ ] 2.2 实现 `src/db/migrations.ts`：基于 `PRAGMA user_version` 的有序迁移，v1 创建 `users`、`invite_codes`、`sessions` 三表
- [ ] 2.3 在 `src/index.ts` 接入 `initDatabase` 启动流程（DB 初始化失败时不监听端口）

## 3. 认证核心服务

- [ ] 3.1 实现 `src/auth/passwords.ts`：scrypt 加盐哈希与 `timingSafeEqual` 校验，格式 `scrypt:16384:8:1:<salt>:<hash>`
- [ ] 3.2 实现 `src/auth/users.ts`：按用户名查用户、创建用户、用户列表、提权（幂等）
- [ ] 3.3 实现 `src/auth/invites.ts`：随机邀请码生成（碰撞重试）、注册时原子消费、列表（含 used/unused/expired 状态）、作废
- [ ] 3.4 实现 `src/auth/sessions.ts`：会话创建/查找/删除、过期清理、cookie 解析与 `Set-Cookie` 写入
- [ ] 3.5 实现 `seedInitialAdmin`：无 admin 时用 `ADMIN_USERNAME`/`ADMIN_PASSWORD` 播种；使用默认密码时打印安全警告

## 4. 中间件与错误处理

- [ ] 4.1 实现 `src/errors.ts`：`ApiError(status, code, message)` 与统一错误中间件（`{error:{code,message}}`，500 不泄露内部细节）
- [ ] 4.2 实现 `src/auth/middleware.ts`：`requireAuth`（cookie → session → `res.locals.user`）与 `requireAdmin`（非 admin 403）

## 5. REST 路由

- [ ] 5.1 实现 `src/routes/auth.ts`：`POST /api/auth/register`（校验 + 事务注册 + 建会话）、`POST /api/auth/login`、`POST /api/auth/logout`、`GET /api/auth/me`
- [ ] 5.2 实现 `src/routes/admin.ts`：`POST /api/admin/invites`、`GET /api/admin/invites`、`DELETE /api/admin/invites/:code`、`GET /api/admin/users`、`POST /api/admin/users/:id/promote`
- [ ] 5.3 在 `createApp` 中挂载两个 router，确认 `/api/health` 与 WS echo 不受影响

## 6. 自动化测试

- [ ] 6.1 `apps/server/package.json` 增加 `"test": "tsx --test tests/**/*.test.ts"`（复用 tsx，不新增依赖）
- [ ] 6.2 编写认证测试：admin 播种、注册消费邀请码（复用/过期 400）、登录/me/logout、401/403 边界
- [ ] 6.3 编写 admin 测试：生成/列表/作废邀请码、用户列表与提权幂等、非 admin 403

## 7. 验收与文档

- [ ] 7.1 `pnpm --dir apps/server type-check` 与 `pnpm --dir apps/server test` 通过
- [ ] 7.2 手工冒烟：`.env.example` 复制为 `.env`，启动后用 cookie jar 完成 admin 生成邀请码 → 新用户注册 → 登录 → 提权全流程
- [ ] 7.3 更新 `docs/handoff.md` 里程碑状态（M1.1a 完成）与 `README.md`（如涉及启动说明变化）
