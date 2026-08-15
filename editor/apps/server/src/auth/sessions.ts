import { randomBytes } from 'node:crypto'

import type Database from 'better-sqlite3'

import type { PublicUser, UserRow } from './users.js'
import { toPublicUser } from './users.js'

export const SESSION_COOKIE = 'ellia_session'

export interface SessionWithUser {
  token: string
  user: PublicUser
  expires_at: string
}

export function generateSessionToken(): string {
  return randomBytes(32).toString('base64url')
}

export function createSession(
  db: Database.Database,
  userId: string,
  ttlDays: number,
): SessionWithUser {
  const token = generateSessionToken()
  const createdAt = new Date().toISOString()
  const expiresAt = new Date(Date.now() + ttlDays * 24 * 60 * 60 * 1000).toISOString()
  db.prepare(
    'INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)',
  ).run(token, userId, createdAt, expiresAt)

  const userRow = db.prepare('SELECT * FROM users WHERE id = ?').get(userId) as
    | UserRow
    | undefined
  if (!userRow) throw new Error(`session created for missing user ${userId}`)
  return { token, user: toPublicUser(userRow), expires_at: expiresAt }
}

/** 查找有效会话；过期会话就地清理。 */
export function findSessionWithUser(
  db: Database.Database,
  token: string,
): SessionWithUser | undefined {
  deleteExpiredSessions(db)
  const row = db
    .prepare(
      `SELECT s.token AS token, s.expires_at AS expires_at,
              u.id AS id, u.username AS username, u.role AS role, u.created_at AS created_at
       FROM sessions s
       JOIN users u ON u.id = s.user_id
       WHERE s.token = ?`,
    )
    .get(token) as
    | {
        token: string
        expires_at: string
        id: string
        username: string
        role: 'user' | 'admin'
        created_at: string
      }
    | undefined
  if (!row) return undefined
  return {
    token: row.token,
    expires_at: row.expires_at,
    user: {
      id: row.id,
      username: row.username,
      role: row.role,
      created_at: row.created_at,
    },
  }
}

export function deleteSession(db: Database.Database, token: string): void {
  db.prepare('DELETE FROM sessions WHERE token = ?').run(token)
}

export function deleteExpiredSessions(db: Database.Database): void {
  db.prepare('DELETE FROM sessions WHERE expires_at <= ?').run(new Date().toISOString())
}

export function parseSessionCookie(cookieHeader: string): string | undefined {
  for (const part of cookieHeader.split(';')) {
    const [name, ...rest] = part.trim().split('=')
    if (name === SESSION_COOKIE && rest.length > 0) {
      return rest.join('=')
    }
  }
  return undefined
}

export function serializeSessionCookie(
  token: string,
  maxAgeSeconds: number,
  options: { secure?: boolean },
): string {
  const attributes = [
    `${SESSION_COOKIE}=${token}`,
    'Path=/',
    'HttpOnly',
    'SameSite=Lax',
    `Max-Age=${Math.floor(maxAgeSeconds)}`,
  ]
  if (options.secure) attributes.push('Secure')
  return attributes.join('; ')
}

export function clearSessionCookie(): string {
  return `${SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`
}
