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
