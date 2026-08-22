/**
 * # API 配置
 *
 * 集中管理所有后端 API 端点，支持双模式运行：
 * - **Mock 模式**（`USE_REAL_API=false`，默认）：前端完全离线，数据来自本地 mock，
 *   行为与现有版本完全一致 —— 支持前端单独部署（纯静态托管即可）。
 * - **真实模式**（`USE_REAL_API=true`）：对接后端 Ellia Mythos API
 *   （FastAPI，所有业务端点统一挂在 `/api/v1` 前缀下）。
 *
 * ## 切换真实 API
 *
 * 1. 后端部署就绪后，按部署形态设置 `API_BASE`（默认 `''` 走同源 `/api` 前缀）
 * 2. 将 `USE_REAL_API` 改为 `true`
 *
 * ## 部署与连接（后端负责 CORS / 网关，前端仅需此配置）
 *
 * - 后端当前**未配置 CORSMiddleware**：开发期请用 Vite 代理
 *   （`vite.config.ts` 的 `server.proxy`：`/api` → 后端地址，如 `http://localhost:8000`），
 *   生产由后端/网关配置跨域或同域部署。
 * - 鉴权双通道：
 *   - 业务请求带 `Authorization: Bearer <access_token>`（JWT，默认 15 分钟过期）；
 *   - 刷新令牌存 **HttpOnly Cookie**（`mythos_refresh`，path=/api/v1/auth，SameSite=Strict），
 *     前端读不到，续期靠 `POST /api/v1/auth/refresh`（浏览器自动带 Cookie）。
 * - 写操作（POST 等）必须带 `Request-ID: <uuid>` 头，后端按幂等/防重放（相同 ID 重复请求返回 409）。
 * - 错误响应统一为 **RFC 9457 ProblemDetails**：`{type,title,status,detail,instance}`，
 *   媒体类型 `application/problem+json`；不要依赖普通 `{detail}` 结构。
 *
 * ## 端点一览（与后端 `mythos/src/mythos/endpoints` 逐一对齐）
 *
 * | 分组     | 方法 | 完整路径                          | 鉴权   | 说明                                    |
 * |----------|------|-----------------------------------|--------|-----------------------------------------|
 * | auth     | POST | `/api/v1/auth/register`           | 无     | 注册 → `{access_token,token_type,expires_in}` + Set-Cookie |
 * | auth     | POST | `/api/v1/auth/login`              | 无     | 密码登录（同上）                        |
 * | auth     | POST | `/api/v1/auth/refresh`            | Cookie | 刷新 access token（无 body）            |
 * | auth     | POST | `/api/v1/auth/logout`             | Bearer | 登出（删除 refresh Cookie）             |
 * | credits  | GET  | `/api/v1/credits`                 | Bearer | 余额 `{vtb, version}`（乐观锁版本号）   |
 * | files    | GET  | `/api/v1/files/ls|tree|version...`| Bearer | 文件系统（后续模块接入，见 docs）       |
 * | progress | GET  | `/api/v1/progress`                | Bearer | 进度 `{unlocked_nodes,frontier_nodes,...}`（后续模块） |
 * | hints    | GET  | `/api/v1/hints`                   | Bearer | 提示列表（后续模块）                    |
 * | ...      |      | `achievement/tasks/scripts/validations/vac` | Bearer | 其余模块，见后端 docs/api/        |
 *
 * 注：后端**不存在** `/auth/validate`、`/auth/token-login` 端点；
 * 会话恢复用 `POST /auth/refresh`，"密钥登录"在真实模式下即"凭 refresh Cookie 续期进桌面"。
 */

/** 后端 API 基地址。默认空串 = 同源相对路径（`/api/...`，配合 Vite 代理或同域部署） */
export const API_BASE = ''

/** 是否启用真实 API 调用。false 时走 mock 逻辑，行为与现有完全一致（单独部署能力） */
export const USE_REAL_API = false

/** 鉴权端点（后端 prefix `/auth`） */
export const AUTH_ENDPOINTS = {
  /** POST — 注册：`{username, password}` → `{access_token, token_type, expires_in}` + Set-Cookie refresh */
  register: `${API_BASE}/api/v1/auth/register`,
  /** POST — 密码登录：`{username, password}` → 同上 */
  login: `${API_BASE}/api/v1/auth/login`,
  /** POST — 刷新 access token：无 body，靠 HttpOnly refresh Cookie（浏览器自动携带） */
  refresh: `${API_BASE}/api/v1/auth/refresh`,
  /** POST — 登出：Bearer，后端删除 refresh Cookie */
  logout: `${API_BASE}/api/v1/auth/logout`,
} as const

/** 代币端点（后端 prefix `/credits`，均需 Bearer） */
export const CREDITS_ENDPOINTS = {
  /** GET — 玩家代币余额：`{vtb: number, version: number}`（version 为乐观锁版本号） */
  balances: `${API_BASE}/api/v1/credits`,
} as const

/**
 * 文件系统端点（后端 prefix `/files`，均需 Bearer）。
 * 面向玩家的浏览应使用**动态树**（`/files/d/*`）：合并玩家 Artifact（如存档恢复报告），
 * 静态树 `/files/*` 只含启动期冻结文件。
 */
export const FILES_ENDPOINTS = {
  /** GET ?path= — 动态目录列表：`{path, directories, files, tree_version}` */
  dynamicList: `${API_BASE}/api/v1/files/d/ls`,
  /** GET ?path= — 动态目录树（递归，含全部后代） */
  dynamicTree: `${API_BASE}/api/v1/files/d/tree`,
  /** GET — 动态树版本（`If-None-Match` 协商，命中返回 304） */
  dynamicVersion: `${API_BASE}/api/v1/files/d/version`,
  /**
   * GET — 文件内容预签名 URL：`{url, expires_at, content_token}`。
   * 先拿 URL 再 fetch 对象存储读取内容；预签名 URL **不持久化**。
   */
  contentUrl: (fileId: string, contentToken: string) =>
    `${API_BASE}/api/v1/files/${fileId}/${contentToken}/content-url`,
} as const

/**
 * 出题器发布题库接入（自动发现）。
 * 出题器（desktop_designer）审核通过的题目导出 published-questions.json 后，
 * 把开关置为 true 并把 URL 指向该静态文件，游戏启动时自动注册进谜题列表。
 * 默认关闭，对现有行为零影响。
 */
export const USE_PUBLISHED_QUESTIONS = false
/** 已发布题库 JSON 地址（出题器 public/ 静态托管或其他可达静态地址） */
export const PUBLISHED_QUESTIONS_URL = 'http://localhost:5174/published-questions.json'
