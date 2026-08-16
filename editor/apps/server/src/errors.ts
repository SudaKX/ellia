import type { ErrorRequestHandler, RequestHandler } from 'express'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export const notFoundHandler: RequestHandler = (_req, _res, next) => {
  next(new ApiError(404, 'NOT_FOUND', 'Not found'))
}

export const errorHandler: ErrorRequestHandler = (error, _req, res, _next) => {
  if (error instanceof ApiError) {
    res.status(error.status).json({ error: { code: error.code, message: error.message } })
    return
  }
  if (
    error instanceof Error &&
    'type' in error &&
    (error as { type?: unknown }).type === 'entity.too.large'
  ) {
    res.status(413).json({ error: { code: 'FILE_TOO_LARGE', message: '文件超过大小上限' } })
    return
  }
  console.error('[ellia-server] unhandled error:', error)
  res.status(500).json({ error: { code: 'INTERNAL', message: 'Internal server error' } })
}
