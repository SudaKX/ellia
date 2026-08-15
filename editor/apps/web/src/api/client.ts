export class ApiClientError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiClientError'
  }
}

interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined && !headers.has('content-type')) {
    headers.set('content-type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(path, { ...init, headers, credentials: 'include' })
  } catch {
    throw new ApiClientError(0, 'NETWORK', '无法连接服务器，请确认服务已启动')
  }

  if (response.status === 204) return undefined as T

  const text = await response.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }

  if (!response.ok) {
    const error = (body as ApiErrorBody | null)?.error
    throw new ApiClientError(
      response.status,
      error?.code ?? 'UNKNOWN',
      error?.message ?? `请求失败（HTTP ${response.status}）`,
    )
  }
  return body as T
}

export function jsonBody(value: unknown): string {
  return JSON.stringify(value)
}
