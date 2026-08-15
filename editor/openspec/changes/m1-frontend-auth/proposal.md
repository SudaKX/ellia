# Proposal: m1-frontend-auth

## Why

M1.1a 提供用户管理 API 后，如果只能 curl 验证，切片对用户不可见。本 change 为这些 API 配套可访问的 Web 界面，使“注册 → 登录 → admin 管理”成为浏览器内可完成的闭环，并建立后续所有页面复用的 auth 状态基础。

## What Changes

- 新增 `apps/web/src/api/`：`fetch` 封装（`credentials: 'include'`）与 auth/admin API 调用。
- 新增 Pinia `auth` store：`user`、`initialized`、`fetchMe/login/register/logout`。
- 新增路由与页面：
  - `/login`：登录表单。
  - `/register`：注册表单（用户名/密码/邀请码）。
  - `/`：登录后的项目列表占位页（M1.2 落地真实列表），展示当前用户与登录状态。
  - `/admin`：邀请码管理（生成/复制/作废/状态列表）+ 用户列表与提权。
- 新增路由守卫：登录才能访问 `/`、`/admin`；已登录跳离 `/login`、`/register`；仅 admin 可访问 `/admin`。
- `App.vue` 增加最小导航（登录态、admin 入口、登出、主题切换）。
- 错误提示与加载态统一处理；无组件库，使用语义化 HTML。
- 新增 Material 3 风格的视觉基础：颜色令牌集中定义于 `src/styles/tokens.css`（light/dark 两套 `--md-sys-color-*`），组件只消费令牌；提供亮/暗主题切换并持久化偏好。

## Capabilities

### New Capabilities

- `auth-web`: 浏览器端认证界面与状态管理，包括登录/注册/管理员面板、路由守卫与基于 cookie 会话的 API 调用。

### Modified Capabilities

<!-- 无既有 capability。 -->

## Impact

- **代码**：`apps/web/src`（新增 `api/`、`stores/auth.ts`、`stores/theme.ts`、`styles/tokens.css`、`styles/base.css`、`views/`；修改 `router/index.ts`、`App.vue`、`main.ts`、`index.html`）。
- **依赖**：无新增运行时依赖（复用 vue-router、pinia）。
- **联调**：依赖 `m1-backend-auth` 的 REST 契约与 cookie 会话；复用 M0 的 Vite `/api` 代理。
- **API**：不新增后端端点；消费 9 个 auth/admin 端点。
