import { Router } from 'express'

import { requireAdmin, requireAuth } from '../auth/middleware.js'
import { createInvite, listInvites, revokeInvite } from '../auth/invites.js'
import { findUserById, listUsers, promoteUser } from '../auth/users.js'
import { parseInviteTtlSeconds } from '../auth/validation.js'
import { getDatabase } from '../db/database.js'
import { ApiError } from '../errors.js'

export const adminRouter = Router()

adminRouter.use(requireAuth, requireAdmin)

adminRouter.post('/invites', (req, res) => {
  const body = (req.body ?? {}) as Record<string, unknown>
  const ttlSeconds = parseInviteTtlSeconds(body.expires_in_seconds)
  if (ttlSeconds === undefined) {
    throw new ApiError(400, 'VALIDATION', 'expires_in_seconds 需为 60-2592000 的整数秒')
  }

  const createdBy = (res.locals.user as { id: string }).id
  const expiresAt = new Date(Date.now() + ttlSeconds * 1000).toISOString()
  const invite = createInvite(getDatabase(), createdBy, expiresAt)
  res.status(201).json({ code: invite.code, expires_at: invite.expires_at })
})

adminRouter.get('/invites', (_req, res) => {
  res.json({ invites: listInvites(getDatabase()) })
})

adminRouter.delete('/invites/:code', (req, res) => {
  const code = req.params.code
  if (!code) throw new ApiError(400, 'VALIDATION', '邀请码不能为空')
  if (!revokeInvite(getDatabase(), code)) {
    throw new ApiError(404, 'INVITE_NOT_FOUND', '邀请码不存在')
  }
  res.status(204).end()
})

adminRouter.get('/users', (_req, res) => {
  res.json({ users: listUsers(getDatabase()) })
})

adminRouter.post('/users/:id/promote', (req, res) => {
  const db = getDatabase()
  if (!findUserById(db, req.params.id)) {
    throw new ApiError(404, 'USER_NOT_FOUND', '用户不存在')
  }
  const user = promoteUser(db, req.params.id)
  res.json({ user })
})
