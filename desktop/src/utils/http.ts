/**
 * # http — 统一后端请求封装（真实模式专用）
 *
 * 在 `USE_REAL_API=true` 时使用，负责把请求对齐后端 Ellia Mythos API 的约定：
 *
 * - **Bearer 鉴权**：自动附加 `Authorization: Bearer <access_token>`（token 取自 useAuth）。
 * - **Request-ID**：写操作（POST 等）自动生成 `Request-ID: <uuid>` 头，
 *   后端按幂等/防重放处理（相同 ID 重复请求返回 409）。
 * - **ProblemDetails 解析**：后端错误统一为 RFC 9457
 *   `{type,title,status,detail,instance}`（application/problem+json），
 *   本封装解析后抛 `ApiError`，调用方可按 `error.status` / `error.type` 分支处理。
 *
 * ## 401 刷新策略（不在本封装内自动重放）
 *
 * access token 默认 15 分钟过期。收到 401 时，调用方应先尝试
 * `useAuth().refreshToken()`（`POST /api/v1/auth/refresh`，靠 HttpOnly Cookie 换新 token），
 * 成功后再重放原请求；失败则清除会话回登录页。
 * 刻意不在此处自动重放——避免与 useAuth 循环依赖，刷新编排由鉴权/业务层负责。
 *
 * ## Mock 模式说明
 *
 * 本封装**只服务真实模式**。Mock 模式（`USE_REAL_API=false`）下调用方应走各自的
 * 本地 mock 分支，不应调用 `apiFetch`（否则会发起无意义的网络请求）。
 */

import { useAuth } from '@/composables/useAuth'

/** 后端错误：RFC 9457 ProblemDetails 的解析结果 */
export class ApiError extends Error {
  /** Problem 类型（绝对 URL），如 `https://problems.invalid/ellia/problems/access-token-invalid` */
  type: string
  /** 人类可读标题，如 "Invalid username or password" */
  title: string
  /** HTTP 状态码 */
  status: number
  /** 详细描述（可选） */
  detail?: string
  /** 原始 ProblemDetails 对象（含扩展字段，如 validations 的 errors） */
  problem: Record<string, unknown>

  constructor(problem: Record<string, unknown>) {
    const title = typeof problem.title === 'string' ? problem.title : 'Request failed'
    super(title)
    this.name = 'ApiError'
    this.type = typeof problem.type === 'string' ? problem.type : 'about:blank'
    this.title = title
    this.status = typeof problem.status === 'number' ? problem.status : 0
    this.detail = typeof problem.detail === 'string' ? problem.detail : undefined
    this.problem = problem
  }
}

/** 生成 UUID v4（写操作 Request-ID 用；无 crypto.randomUUID 时降级伪随机） */
function uuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export interface ApiRequestOptions {
  /** HTTP 方法，默认 GET */
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** JSON 请求体（自动设置 Content-Type: application/json） */
  body?: unknown
  /** 是否附加 Bearer token，默认 true（refresh 等端点传 false） */
  auth?: boolean
  /** 是否自动生成 Request-ID 头，默认 true（写操作防重放；GET 无此头） */
  requestId?: boolean
  /** 自定义请求头（会与自动头合并，可覆盖） */
  headers?: Record<string, string>
}

/**
 * 发起一次对齐后端约定的请求。
 *
 * @param path    完整 URL（通常为 `AUTH_ENDPOINTS.xxx` 等已拼接 API_BASE 的端点）
 * @param options 方法 / body / 鉴权与请求头选项
 * @returns 解析后的响应 JSON；204 无内容时返回 undefined
 * @throws {ApiError} 后端返回非 2xx 时（含 RFC 9457 ProblemDetails 解析）
 */
export async function apiFetch<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const {
    method = 'GET',
    body,
    auth = true,
    requestId = true,
    headers: extraHeaders,
  } = options

  const headers: Record<string, string> = { ...extraHeaders }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = useAuth().getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }
  if (requestId && method !== 'GET') {
    headers['Request-ID'] = uuid()
  }

  let res: Response
  try {
    res = await fetch(path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (cause) {
    // 网络层失败（后端不可达 / 代理未配置等），包装成 ApiError 便于调用方统一处理
    throw new ApiError({
      type: 'about:blank',
      title: cause instanceof Error ? cause.message : 'Network request failed',
      status: 0,
    })
  }

  if (res.status === 204) return undefined as T

  const text = await res.text()
  const data: unknown = text ? JSON.parse(text) : null

  if (!res.ok) {
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      throw new ApiError(data as Record<string, unknown>)
    }
    // 非 ProblemDetails 的兜底
    throw new ApiError({ type: 'about:blank', title: res.statusText, status: res.status })
  }
  return data as T
}
