# Design: m1-backend-auth

## Context

`apps/server` 目前只有 M0 骨架（`createApp` + `/api/health` + WS echo），尚无数据库、认证或路由分层。技术约束见 proposal.md 与 `docs/plan-v1.md`：SQLite 必须用 better-sqlite3（已确认决策）；后端权威状态；M1 只做用户管理切片。

## Goals / Non-Goals

**Goals:**

- 建立可扩展的 DB 初始化/迁移骨架（后续 `projects`/`entities` 表沿用）。
- 提供 cookie 会话认证，使 REST 与后续 WS 升级共用同一套会话。
- 统一错误契约，前端 `m1-frontend-auth` 可稳定消费。

**Non-Goals:**

- 不做 `projects`/`entities`/`entity_blobs`/`entity_patches` 表（M1.2 通过新迁移加入）。
- 不做限流、密码重置、refresh token、OAuth、多租户。
- 不引入 zod/bcrypt 等额外运行时依赖。

## Decisions

### 1. better-sqlite3 + 版本化迁移

- 用 `better-sqlite3`（sync API）在请求内直接执行短查询；SQLite 本地查询为微秒级，无需 async 池。
- 启动时执行 `src/db/migrations.ts` 中的有序迁移数组，`PRAGMA user_version` 记录版本；迁移 1 创建 `users`、`invite_codes`、`sessions`，全部在事务中完成。
- 替代方案：`node:sqlite`（与已确认决策冲突，排除）；ORM（本切片过度设计）。
- 后续切片只追加迁移，不回改已应用迁移。

### 2. 表结构（迁移 v1）

```sql
users(
  id TEXT PRIMARY KEY,               -- crypto.randomUUID()
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user','admin')),
  created_at TEXT NOT NULL
)

invite_codes(
  code TEXT PRIMARY KEY,
  created_by TEXT NOT NULL REFERENCES users(id),
  expires_at TEXT NOT NULL,          -- ISO 8601 UTC
  used_by TEXT REFERENCES users(id),
  used_at TEXT
)

sessions(
  token TEXT PRIMARY KEY,            -- 32 字节随机数 base64url
  user_id TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
)
```

时间统一存 ISO 8601 UTC 字符串；`username` 用 `COLLATE NOCASE` 保证大小写不敏感唯一。

### 3. 密码：内置 `crypto.scrypt`

- 存储格式 `scrypt:16384:8:1:<saltHex>:<hashHex>`；盐 16 字节、keylen 64。
- 校验用 `crypto.timingSafeEqual`；固定参数写入存储串，未来升级参数时按前缀识别。
- 替代方案：bcrypt/argon2（需原生依赖与 allowBuilds 配置，收益不足以抵消维护成本）。

### 4. 会话：服务端 session 表 + HttpOnly cookie

- 登录/注册成功后生成 32 字节 `base64url` token，插入 `sessions`（默认 30 天 TTL），并 `Set-Cookie: ellia_session=...; HttpOnly; SameSite=Lax; Path=/`（`NODE_ENV=production` 时加 `Secure`）。
- 登出删除该行并清 cookie；`me` 联表返回 `{id, username, role}`。
- 替代方案：
  - Bearer + localStorage：token 暴露给 JS（XSS 风险），WS 握手需手动传 token；cookie 会自动携带。
  - JWT：无法主动吊销，复杂度更高；单机服务端会话表足够。
- CSRF：`SameSite=Lax` 阻止跨站 POST 携带 cookie；v1 不再加 CSRF token。

### 5. 中间件与错误契约

- `requireAuth`：读 cookie → 查 `sessions JOIN users` → 过期则删除并 401；通过 `res.locals.user` 传递用户（避免扩展 Express Request 类型）。
- `requireAdmin`：在 `requireAuth` 后检查 `role === 'admin'`，否则 403。
- 统一 `ApiError(status, code, message)` + Express error middleware，响应恒为 `{ error: { code, message } }`；未捕获异常 → 500 `INTERNAL`（不含内部细节）。
- 状态码约定：401 未认证、403 权限不足、404 资源不存在、409 唯一性冲突、400 参数/邀请码错误。

### 6. 输入校验与规则（设计级常量，可调且不影响 spec）

- `username`：trim 后 3–32 字符，仅 `[A-Za-z0-9_-]`。
- `password`：8–128 字符。
- `expires_in_seconds`：整数，60–2_592_000（1 分钟–30 天），缺省 604800（7 天）。
- 邀请码：`crypto.randomBytes(12).toString('base64url')`（16 字符）；主键冲突时重试一次。
- 注册原子操作：验证邀请码 → `INSERT user` + `UPDATE invite_codes SET used_*` + `INSERT session` 包在 `db.transaction` 中。

### 7. 模块布局

```text
apps/server/src/
├── db/
│   ├── database.ts        # 打开连接、PRAGMA、导出单例
│   └── migrations.ts      # 有序迁移 + PRAGMA user_version
├── auth/
│   ├── passwords.ts       # scrypt hash/verify
│   ├── sessions.ts        # 创建/查找/删除会话 + cookie 解析/写入
│   ├── invites.ts         # 生成/消费/列表/作废
│   ├── users.ts           # 注册/登录/列表/提权/seed admin
│   └── middleware.ts      # requireAuth / requireAdmin
├── routes/
│   ├── auth.ts            # /api/auth/*
│   └── admin.ts           # /api/admin/*
├── errors.ts              # ApiError + error middleware
├── config.ts              # 扩展 DATABASE_PATH / SESSION_TTL_DAYS
└── index.ts               # initDb → seedAdmin → listen
```

### 8. 启动顺序与 admin 播种

- `index.ts`：`loadConfig` → `initDatabase`（含迁移）→ `seedInitialAdmin` → `createServer(createApp())` → 监听。
- 播种规则：`SELECT role='admin' FROM users` 存在则跳过；不存在则用 `.env` 账号创建；`ADMIN_PASSWORD` 未配置（默认 `admin`）时打印 `[ellia-server] WARNING: using insecure default admin password`。

### 9. 测试策略

- 新增 dev script：`"test": "tsx --test tests/**/*.test.ts"`（复用已有 tsx，不新增依赖）。
- 每个测试用临时目录 DB 初始化，覆盖：admin 播种、注册/邀请码一次性、登录/me/logout、403/401 边界、promote。
- 手工冒烟：`.env.example` → 启动 → curl 走 cookie jar 完成 admin 闭环。

## Risks / Trade-offs

- [better-sqlite3 原生模块在 Node 24/Windows 的预编译失败] → 在 `pnpm-workspace.yaml` 增加 `allowBuilds.better-sqlite3=true`；若安装失败改用其官方预编译资产并记录。
- [cookie 会话受 CSRF/浏览器限制影响后续 API 客户端] → v1 只服务同源 web；后续需要非浏览器客户端时再加 Bearer 通道，不影响 spec。
- [无限流，登录/注册接口可被暴力请求] → v1 明确不做（见 Non-Goals）；部署侧可用反向代理限流。
- [`COLLATE NOCASE` 仅覆盖 ASCII 大小写] → 用户名字符集被限制为 ASCII 安全集，风险不存在。
- [迁移只追加，早期 schema 错误无法就地修复] → v1 无生产数据，开发期可删除 `data/ellia.db` 重建。

## Migration Plan

1. `pnpm --dir apps/server add better-sqlite3 && pnpm --dir apps/server add -D @types/better-sqlite3`，更新 lockfile 与 allowBuilds。
2. 落地代码后删除本地旧 `apps/server/data/`（当前为空/不存在），启动即自动建库。
3. 回滚：删除 `apps/server/data/ellia.db` 即回到未初始化状态。
