# Tasks: m1-frontend-auth

## 1. API 客户端

- [x] 1.1 实现 `src/api/types.ts`：`AuthUser`、`InviteCode`、`UserSummary` 与请求/响应接口（与后端 spec 对齐）
- [x] 1.2 实现 `src/api/client.ts`：fetch 封装（`credentials:'include'`、JSON 编解码、`ApiClientError`/网络错误归一）
- [x] 1.3 实现 `src/api/auth.ts` 与 `src/api/admin.ts`：me/login/register/logout、invites CRUD、users list/promote

## 2. 认证状态

- [x] 2.1 实现 `src/stores/auth.ts`：`user`、`initialized`、`fetchMe/initialize/login/register/logout`
- [x] 2.2 修改 `src/main.ts`：创建 pinia/router 后、`app.mount` 前 `await auth.initialize()`

## 3. 路由与守卫

- [x] 3.1 在 `src/router/index.ts` 定义 `/login`、`/register`、`/`、`/admin` 及 meta（`guestOnly`/`requiresAuth`/`requiresAdmin`）
- [x] 3.2 实现 `beforeEach` 守卫：未登录跳 `/login`（带 redirect）、已登录跳离 guest 页、非 admin 跳 `/`

## 4. 页面实现

- [x] 4.1 实现 `LoginView.vue`：用户名/密码表单、提交禁用、错误提示、注册入口、成功后跳转
- [x] 4.2 实现 `RegisterView.vue`：用户名/密码/邀请码表单、服务端错误展示、成功后跳转
- [x] 4.3 实现 `HomeView.vue`：登录态占位页（显示当前用户，标注项目列表 M1.2 落地）
- [x] 4.4 实现 `AdminView.vue` 邀请码面板：生成（1h/1d/7d/30d）、列表状态、复制（失败降级提示手动复制）、作废
- [x] 4.5 实现 `AdminView.vue` 用户面板：用户列表、`user` 角色提权按钮、提权后刷新列表

## 5. 应用外壳

- [x] 5.1 重写 `App.vue`：顶部导航（品牌、当前用户、admin 入口、登出）、`<RouterView>`
- [x] 5.2 添加最小全局样式，保证表单标签、错误提示（`role="alert"`）与按钮状态可访问

## 6. 验收

- [x] 6.1 `pnpm --dir apps/web type-check` 与 `pnpm build` 通过
- [x] 6.2 配合 `m1-backend-auth` 手工冒烟：admin 登录 → 生成邀请码 → 新窗口注册/登录 → 提权 → 登出重登
- [x] 6.3 校验守卫：匿名访问 `/`、`/admin` 被重定向；user 访问 `/admin` 被重定向；已登录访问 `/login` 被重定向
- [x] 6.4 更新 `docs/handoff.md` 里程碑状态（M1.1b 完成）

## 7. Material 3 主题与令牌

- [x] 7.1 实现 `src/styles/tokens.css`：集中定义 light/dark 两套 `--md-sys-color-*` 与应用语义令牌，作为全站唯一颜色来源
- [x] 7.2 实现 `src/stores/theme.ts` 与 `index.html` 内联脚本：主题切换、localStorage 持久化、跟随系统偏好、首屏防闪烁
- [x] 7.3 实现 `src/styles/base.css`：M3 风格表单/按钮/卡片/表格/提示，组件只消费令牌不硬编码色值
