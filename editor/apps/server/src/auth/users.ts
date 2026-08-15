import { randomUUID } from 'node:crypto'

import type Database from 'better-sqlite3'

import type { ServerConfig } from '../config.js'
import { hashPassword } from './passwords.js'

export type UserRole = 'user' | 'admin'

export interface UserRow {
  id: string
  username: string
  password_hash: string
  role: UserRole
  created_at: string
}

export interface PublicUser {
  id: string
  username: string
  role: UserRole
  created_at: string
}

export function toPublicUser(row: UserRow): PublicUser {
  return {
    id: row.id,
    username: row.username,
    role: row.role,
    created_at: row.created_at,
  }
}

export function findUserByUsername(db: Database.Database, username: string): UserRow | undefined {
  const row = db.prepare('SELECT * FROM users WHERE username = ?').get(username) as
    | UserRow
    | undefined
  return row
}

export function findUserById(db: Database.Database, id: string): UserRow | undefined {
  const row = db.prepare('SELECT * FROM users WHERE id = ?').get(id) as UserRow | undefined
  return row
}

export function countAdmins(db: Database.Database): number {
  const row = db
    .prepare("SELECT COUNT(*) AS count FROM users WHERE role = 'admin'")
    .get() as { count: number }
  return row.count
}

export function createUser(
  db: Database.Database,
  input: { username: string; passwordHash: string; role?: UserRole },
): PublicUser {
  const id = randomUUID()
  const createdAt = new Date().toISOString()
  db.prepare(
    'INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)',
  ).run(id, input.username, input.passwordHash, input.role ?? 'user', createdAt)
  return { id, username: input.username, role: input.role ?? 'user', created_at: createdAt }
}

export function listUsers(db: Database.Database): PublicUser[] {
  const rows = db
    .prepare('SELECT * FROM users ORDER BY created_at ASC, username ASC')
    .all() as UserRow[]
  return rows.map(toPublicUser)
}

export function promoteUser(db: Database.Database, id: string): PublicUser | undefined {
  const result = db.prepare("UPDATE users SET role = 'admin' WHERE id = ?").run(id)
  if (result.changes === 0) return undefined
  const row = findUserById(db, id)
  return row ? toPublicUser(row) : undefined
}

/** 首次启动播种：已有 admin 时跳过；使用默认密码时打印安全警告。 */
export async function seedInitialAdmin(db: Database.Database, config: ServerConfig): Promise<void> {
  if (countAdmins(db) > 0) return
  createUser(db, {
    username: config.adminUsername,
    passwordHash: await hashPassword(config.adminPassword),
    role: 'admin',
  })
  if (config.adminPassword === 'admin') {
    console.warn('[ellia-server] WARNING: using insecure default admin password "admin"')
  }
}
