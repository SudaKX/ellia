import { randomBytes } from 'node:crypto'

import type Database from 'better-sqlite3'

import { isSqliteConstraintError } from '../db/database.js'

export interface InviteRow {
  code: string
  created_by: string
  expires_at: string
  used_by: string | null
  used_at: string | null
}

export type InviteStatus = 'unused' | 'used' | 'expired'

export interface InviteWithStatus extends InviteRow {
  status: InviteStatus
}

export function generateInviteCode(): string {
  return randomBytes(12).toString('base64url')
}

export function createInvite(
  db: Database.Database,
  createdBy: string,
  expiresAt: string,
): InviteRow {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const code = generateInviteCode()
    try {
      db.prepare(
        'INSERT INTO invite_codes (code, created_by, expires_at) VALUES (?, ?, ?)',
      ).run(code, createdBy, expiresAt)
      return { code, created_by: createdBy, expires_at: expiresAt, used_by: null, used_at: null }
    } catch (error) {
      if (!isSqliteConstraintError(error) || attempt === 2) throw error
    }
  }
  throw new Error('failed to generate a unique invite code')
}

export function findInviteByCode(db: Database.Database, code: string): InviteRow | undefined {
  const row = db.prepare('SELECT * FROM invite_codes WHERE code = ?').get(code) as
    | InviteRow
    | undefined
  return row
}

export type ConsumeInviteResult =
  | { status: 'consumed'; invite: InviteRow }
  | { status: 'not-found' | 'used' | 'expired' }

export function inviteAvailability(
  db: Database.Database,
  code: string,
): 'available' | 'not-found' | 'used' | 'expired' {
  const row = findInviteByCode(db, code)
  if (!row) return 'not-found'
  if (row.used_by !== null || row.used_at !== null) return 'used'
  if (Date.parse(row.expires_at) <= Date.now()) return 'expired'
  return 'available'
}

/** 在注册事务内消费邀请码；状态判断与更新在同一连接上保持原子性。 */
export function consumeInvite(
  db: Database.Database,
  code: string,
  usedBy: string,
): ConsumeInviteResult {
  const availability = inviteAvailability(db, code)
  if (availability !== 'available') return { status: availability }

  const now = new Date().toISOString()
  const result = db
    .prepare(
      `UPDATE invite_codes
       SET used_by = ?, used_at = ?
       WHERE code = ? AND used_by IS NULL AND used_at IS NULL`,
    )
    .run(usedBy, now, code)
  if (result.changes !== 1) return { status: 'used' }

  const row = findInviteByCode(db, code)
  if (!row) return { status: 'not-found' }
  return {
    status: 'consumed',
    invite: { ...row, used_by: usedBy, used_at: now },
  }
}

export function listInvites(db: Database.Database): InviteWithStatus[] {
  const rows = db
    .prepare('SELECT * FROM invite_codes ORDER BY rowid DESC')
    .all()
  return (rows as InviteRow[]).map((row) => ({ ...row, status: inviteStatus(row) }))
}

function inviteStatus(row: InviteRow): InviteStatus {
  if (row.used_by !== null || row.used_at !== null) return 'used'
  if (Date.parse(row.expires_at) <= Date.now()) return 'expired'
  return 'unused'
}

export function revokeInvite(db: Database.Database, code: string): boolean {
  const result = db.prepare('DELETE FROM invite_codes WHERE code = ?').run(code)
  return result.changes > 0
}
