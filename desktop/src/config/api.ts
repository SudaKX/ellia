/**
 * # API 配置
 *
 * 集中管理所有后端 API 端点。
 *
 * ## 切换 Mock / 真实 API
 *
 * 1. 设置 `API_BASE` 为后端地址
 * 2. 将 `USE_REAL_API` 改为 `true`
 *
 * ## 端点一览
 *
 * | 端点    | 方法 | 路径                       | Body                                  |
 * |---------|------|---------------------------|---------------------------------------|
 * | validate | POST | /api/auth/validate        | `{ token: string }`                  |
 * | login    | POST | /api/auth/login           | `{ username: string, password: string }` |
 * | tokenLogin | POST | /api/auth/token-login   | `{ token: string }`                  |
 */

/** 后端 API 基地址。后端就绪后改为实际地址，如 `https://api.example.com` 或 `/api` */
export const API_BASE = ''

/** 是否启用真实 API 调用。false 时走 mock 逻辑，行为与现有完全一致 */
export const USE_REAL_API = false

/** 鉴权相关端点 */
export const AUTH_ENDPOINTS = {
  /** POST — 校验 token 有效性 */
  validate: `${API_BASE}/api/auth/validate`,
  /** POST — 密码登录 */
  login: `${API_BASE}/api/auth/login`,
  /** POST — token 登录（如 key login） */
  tokenLogin: `${API_BASE}/api/auth/token-login`,
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
