# Design: m1-frontend-auth

## Context

`apps/web` 目前只有 M0 占位 `App.vue` 与空路由。Vite dev 代理已把 `/api` 转发到 `apps/server`（`VITE_API_PROXY_TARGET` 可覆盖）。本 change 依赖 `m1-backend-auth` 的 cookie 会话与 `{ error: { code, message } }` 错误契约。

## Goals / Non-Goals

**Goals:**

- 建立后续所有页面复用的 API client、auth store 与路由守卫模式。
- 让 M1.1 后端能力在浏览器内可操作、可验收。

**Non-Goals:**

- 不做项目列表真实数据（`/` 为占位页，M1.2 落地）。
- 不引入组件库、表单库或后端 API schema 校验库。
- 不做“记住我”、多标签页实时同步登录态。

## Decisions

### 1. fetch 封装而非 axios

- `src/api/client.ts` 提供 `request<T>(path, init?)`：统一 `credentials: 'include'`、JSON 编解码、把 `{error:{code,message}}` 映射为 `ApiClientError`。
- 理由：现代浏览器原生支持，零新增依赖；所有页面只需消费这个薄封装。
- 替代方案：axios（本切片收益不大）。

### 2. Pinia auth store + 启动前恢复会话

- `src/stores/auth.ts` 使用 setup store：`user: AuthUser | null`、`initialized`、`fetchMe()`、`login()`、`register()`、`logout()`。
- `main.ts` 在 `app.mount()` 前 `await auth.initialize()`（内部 `fetchMe`，401 视为匿名成功）；挂载后路由守卫只做同步判断，不闪烁登录页。
- 理由：先恢复会话再进入路由，避免守卫内部异步竞态。
- 替代方案：守卫内懒加载 me（首个受保护路由会闪烁）；全局 `onMounted` 恢复（时序不可控）。

### 3. 路由与守卫

```text
/login      meta: { guestOnly: true }
/register   meta: { guestOnly: true }
/           meta: { requiresAuth: true }
/admin      meta: { requiresAuth: true, requiresAdmin: true }
```

- `router.beforeEach`：`requiresAuth && !user` → `/login?redirect=...`；`guestOnly && user` → `/`；`requiresAdmin && user.role !== 'admin'` → `/`。
- 登录/注册成功后导航到 `redirect` 参数或 `/`。

### 4. 页面与组件切分

```text
apps/web/src/
├── api/{client,auth,admin,types}.ts
├── stores/{auth,theme}.ts
├── styles/{tokens,base}.css
├── router/index.ts                 # 路由表 + meta + 守卫
├── App.vue                         # 顶部导航：品牌/主题切换/当前用户/admin 入口/登出
└── views/
    ├── LoginView.vue
    ├── RegisterView.vue
    ├── HomeView.vue                # 项目列表占位 + 当前登录态说明
    └── AdminView.vue               # 邀请码面板 + 用户面板
```

- 表单用原生 `form @submit.prevent` + `v-model`；提交期间按钮 `disabled`。
- `AdminView`：左侧邀请码（`expires_in` 下拉：1h/1d/7d/30d → 秒值；生成后列表刷新；复制用 `navigator.clipboard`，失败时提示手动复制；作废需 `confirm`），右侧用户表（role 为 user 时显示“提权”按钮）。
- 不抽公共组件库；错误提示作为页面内 `role="alert"` 元素，保证可访问性。

### 5. 类型契约

- `src/api/types.ts` 定义 `AuthUser`、`InviteCode`、`UserSummary` 等接口，与后端响应字段一一对应。
- 不放进 `@ellia/puzzle-schema`：该包是谜题域数据事实源，认证 API 类型不属于谜题域；若后续出现第三个消费方再抽共享包。
- 前后端契约以 `m1-backend-auth/specs/user-management/spec.md` 为准；实现时发现字段冲突以 spec 为准修正。

### 6. Cookie 与代理

- 所有请求 `credentials: 'include'`；同源（dev 经 Vite 代理，prod 后续由 Express 托管）自动携带 cookie。
- 不读取/写入 localStorage 中的 token，避免 XSS 暴露面。

### 7. Material 3 风格与颜色令牌

- `src/styles/tokens.css` 是唯一颜色来源：`:root` 定义 light 令牌，`[data-theme='dark']` 定义 dark 令牌，采用 Material 3 语义色（`--md-sys-color-{primary,on-primary,primary-container,...,surface,on-surface,outline,error}`），另加少量应用级语义别名（页面背景、卡片、成功/警告态）。
- `src/styles/base.css` 提供 reset、排版、表单控件、按钮、卡片、表格与 `role="alert"` 的视觉；所有颜色只引用令牌，不在组件 `<style>` 里写死色值。
- `src/stores/theme.ts`（Pinia setup store）：`mode: 'light' | 'dark'`；初始化时读取 `localStorage['ellia-theme']`，无保存值则跟随 `prefers-color-scheme`；`toggle()` 同步写回 localStorage 与 `document.documentElement.dataset.theme`。
- `index.html` 增加极小内联脚本：在首屏 CSS 之前按保存值/系统偏好设置 `data-theme`，避免暗色用户白屏闪烁。
- 不引入 Vue Material / Vuetify 等组件库（与本 change 的 Non-Goals 一致）；M3 通过令牌 + CSS 实现，后续“换色”只需改 tokens.css 或注入不同的 token 文件。
- 主题偏好是界面偏好而非敏感凭证，允许存 localStorage（与 token 的禁用策略不同）。

## Risks / Trade-offs

- [后端未就绪时前端页面报网络错误] → `client.ts` 区分 `ApiClientError`（有 code）与网络错误（`NETWORK`），表单显示“无法连接服务器”。
- [clipboard API 在非安全上下文失败] → 复制失败时选中文本提示手动复制，功能不阻断。
- [启动前 `fetchMe` 延迟首屏] → v1 接受一次本地请求（约毫秒级）；慢时可在 `index.html` 放静态 loading 文案。
- [多标签页登出/登录不同步] → v1 不处理；每个标签页加载时各自 `fetchMe`。
- [暗色首屏闪烁] → `index.html` 内联脚本在样式加载前设置 `data-theme`。

## Migration Plan

- 纯前端增量：无数据迁移；旧 M0 占位内容被替换。
- 上线步骤：先部署 `m1-backend-auth`，再部署本 change；浏览器强刷后即可访问 `/login`。
- 回滚：恢复 M0 的 `App.vue`/空路由即可，后端兼容。
