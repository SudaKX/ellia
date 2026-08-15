# Ellia 谜题在线多人编辑器（editor/）

Mythos 谜题模块的专属在线多人编辑器：多人通过状态同步协作编辑谜题模块，一键导出为合法谜题模块 zip。
完整方案见 [`docs/plan-v1.md`](docs/plan-v1.md)，调研结论与决策见 [`docs/handoff.md`](docs/handoff.md)。

## 仓库布局（pnpm workspace）

```text
editor/
├── pnpm-workspace.yaml
├── package.json                # workspace 根：聚合 dev / build / type-check
├── docs/                       # plan-v1.md / handoff.md
├── apps/
│   ├── web/                    # Vue3 + Vite 前端（Pinia / vue-router，@ → src）
│   └── server/                 # Express 5 + 原生 ws 后端（TypeScript）
└── packages/
    └── puzzle-schema/          # @ellia/puzzle-schema 共享 TS 包（数据结构唯一事实源）
```

- `@ellia/puzzle-schema` 被 `apps/web` 与 `apps/server` 共同 import。
- 开发期：web 走 Vite 代理，`/api`、`/ws` → `http://localhost:3000`（可用环境变量 `VITE_API_PROXY_TARGET` 覆盖）。
- 生产期（后续里程碑）：Express 静态托管 `apps/web/dist`。

## 快速开始

```powershell
pnpm install                # 安装全部 workspace 依赖
pnpm dev                    # 并行启动 server（:3000）与 web（:5173）
pnpm type-check             # 三个包全部类型检查
pnpm build                  # 构建 web 生产包（先 vue-tsc 再 Vite）
pnpm --dir apps/server test # 后端单元测试（node:test + tsx）
```

server 配置读取 `apps/server/.env`（模板见 `apps/server/.env.example`；`.env` 不提交）。首次启动会自动创建 SQLite 数据库（默认 `apps/server/data/ellia.db`）并播种初始 admin。

## 里程碑状态

- [x] **M0 仓库骨架**：workspace 建立、`apps/web` 迁移、`apps/server`（Express 5 + ws echo）可启动、`@ellia/puzzle-schema` 接通
- [x] **M1.1a 后端用户管理**：SQLite（better-sqlite3）、注册/登录/登出/me、一次性邀请码、初始 admin、admin 用户管理（含单元测试）
- [ ] M1.1b 前端认证界面：`/login`、`/register`、`/admin`、Pinia auth 与路由守卫
- [ ] M1.2 项目 CRUD：`projects` 表 + REST CRUD + 前端项目列表
- [ ] M2 数据模型与同步：实体/补丁日志、WS 同步协议、编辑器主界面
- [ ] M3 导出：file-tree.json、`__init__.py` 模板、`puzzles/__init__.py` 合并、zip 打包
