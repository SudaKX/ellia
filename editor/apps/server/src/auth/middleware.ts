import type { Request, RequestHandler } from 'express'

import type { ServerConfig } from '../config.js'
import { getDatabase } from '../db/database.js'
import { ApiError } from '../errors.js'
import type { PublicUser } from './users.js'
import { findSessionWithUser, parseSessionCookie } from './sessions.js'

export const requireAuth: RequestHandler = (req, res, next) => {
  const token = parseSessionCookie(req.headers.cookie ?? '')
  if (!token) {
    next(new ApiError(401, 'UNAUTHORIZED', '未登录'))
    return
  }
  const session = findSessionWithUser(getDatabase(), token)
  if (!session) {
    next(new ApiError(401, 'UNAUTHORIZED', '会话无效或已过期'))
    return
  }
  res.locals.user = session.user
  next()
}

export const requireAdmin: RequestHandler = (_req, res, next) => {
  const user = res.locals.user as PublicUser | undefined
  if (user?.role !== 'admin') {
    next(new ApiError(403, 'FORBIDDEN', '需要 admin 权限'))
    return
  }
  next()
}

/** 从 app.locals 读取运行配置（createApp 注入，测试可覆盖）。 */
export function getServerConfig(req: Request): ServerConfig {
  return req.app.locals.config as ServerConfig
}
