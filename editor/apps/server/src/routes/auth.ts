import { Router } from 'express'
import type { Response } from 'express'

import { getServerConfig, requireAuth } from '../auth/middleware.js'
import { consumeInvite, inviteAvailability } from '../auth/invites.js'
import { hashPassword, verifyPassword } from '../auth/passwords.js'
import {
  clearSessionCookie,
  createSession,
  deleteSession,
  parseSessionCookie,
  serializeSessionCookie,
} from '../auth/sessions.js'
import type { PublicUser } from '../auth/users.js'
import { createUser, findUserByUsername } from '../auth/users.js'
import {
  isValidPassword,
  isValidUsername,
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH,
} from '../auth/validation.js'
import type { ServerConfig } from '../config.js'
import { getDatabase, isSqliteConstraintError } from '../db/database.js'
import { ApiError } from '../errors.js'

export const authRouter = Router()

authRouter.post('/register', async (req, res) => {
  const body = (req.body ?? {}) as Record<string, unknown>
  const username = typeof body.username === 'string' ? body.username.trim() : ''
  const password = typeof body.password === 'string' ? body.password : ''
  const inviteCode = typeof body.invite_code === 'string' ? body.invite_code.trim() : ''

  if (!isValidUsername(username)) {
    throw new ApiError(400, 'VALIDATION', '用户名需为 3-32 位字母、数字、_ 或 -')
  }
  if (!isValidPassword(password)) {
    throw new ApiError(
      400,
      'VALIDATION',
      `密码长度需为 ${MIN_PASSWORD_LENGTH}-${MAX_PASSWORD_LENGTH} 个字符`,
    )
  }
  if (!inviteCode) {
    throw new ApiError(400, 'VALIDATION', '邀请码不能为空')
  }

  const passwordHash = await hashPassword(password)
  const db = getDatabase()
  const config = getServerConfig(req)
  let created: { user: PublicUser; token: string }
  try {
    created = db.transaction(() => {
      const availability = inviteAvailability(db, inviteCode)
      if (availability === 'not-found') {
        throw new ApiError(400, 'INVALID_INVITE', '邀请码无效')
      }
      if (availability === 'used') {
        throw new ApiError(400, 'INVITE_USED', '邀请码已被使用')
      }
      if (availability === 'expired') {
        throw new ApiError(400, 'INVITE_EXPIRED', '邀请码已过期')
      }

      const newUser = createUser(db, { username, passwordHash })
      const consumed = consumeInvite(db, inviteCode, newUser.id)
      if (consumed.status !== 'consumed') {
        throw new ApiError(400, 'INVITE_USED', '邀请码已被使用')
      }
      const session = createSession(db, newUser.id, config.sessionTtlDays)
      return { user: newUser, token: session.token }
    })()
  } catch (error) {
    if (isSqliteConstraintError(error)) {
      throw new ApiError(409, 'USERNAME_TAKEN', '用户名已存在')
    }
    throw error
  }

  setSessionCookie(res, created.token, config)
  res.status(201).json({ user: created.user })
})

authRouter.post('/login', async (req, res) => {
  const body = (req.body ?? {}) as Record<string, unknown>
  const username = typeof body.username === 'string' ? body.username.trim() : ''
  const password = typeof body.password === 'string' ? body.password : ''
  if (!username || !password) {
    throw new ApiError(400, 'VALIDATION', '用户名和密码不能为空')
  }

  const db = getDatabase()
  const userRow = findUserByUsername(db, username)
  if (!userRow || !(await verifyPassword(password, userRow.password_hash))) {
    throw new ApiError(401, 'INVALID_CREDENTIALS', '用户名或密码错误')
  }

  const config = getServerConfig(req)
  const session = createSession(db, userRow.id, config.sessionTtlDays)
  setSessionCookie(res, session.token, config)
  res.json({ user: session.user })
})

authRouter.post('/logout', (req, res) => {
  const token = parseSessionCookie(req.headers.cookie ?? '')
  if (token) deleteSession(getDatabase(), token)
  res.setHeader('Set-Cookie', clearSessionCookie())
  res.status(204).end()
})

authRouter.get('/me', requireAuth, (_req, res) => {
  res.json({ user: res.locals.user as PublicUser })
})

function setSessionCookie(res: Response, token: string, config: ServerConfig): void {
  const maxAgeSeconds = config.sessionTtlDays * 24 * 60 * 60
  res.setHeader(
    'Set-Cookie',
    serializeSessionCookie(token, maxAgeSeconds, { secure: config.secureCookies }),
  )
}
