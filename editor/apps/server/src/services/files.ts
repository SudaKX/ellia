import type { FileRecord } from '@ellia/puzzle-schema'
import type Database from 'better-sqlite3'

import { getDatabase } from '../db/database.js'

interface FileRow {
  id: string
  original_name: string | null
  media_type: string
  module: string | null
  size: number
  sha256: string
  uploaded_by: string
  created_at: string
}

export interface InsertFileInput {
  id: string
  originalName: string | null
  mediaType: string
  module: string | null
  size: number
  sha256: string
  uploadedBy: string
}

export function insertFile(
  input: InsertFileInput,
  db: Database.Database = getDatabase(),
): FileRecord {
  const createdAt = new Date().toISOString()
  db.prepare(
    `INSERT INTO files (id, original_name, media_type, module, size, sha256, uploaded_by, created_at)
     VALUES (@id, @original_name, @media_type, @module, @size, @sha256, @uploaded_by, @created_at)`,
  ).run({
    id: input.id,
    original_name: input.originalName,
    media_type: input.mediaType,
    module: input.module,
    size: input.size,
    sha256: input.sha256,
    uploaded_by: input.uploadedBy,
    created_at: createdAt,
  })
  return toFileRecord(findFileRow(db, input.id)!)
}

export function findFileById(
  id: string,
  db: Database.Database = getDatabase(),
): FileRecord | undefined {
  const row = findFileRow(db, id)
  return row ? toFileRecord(row) : undefined
}

export function listFiles(db: Database.Database = getDatabase()): FileRecord[] {
  const rows = db.prepare('SELECT * FROM files ORDER BY created_at DESC').all() as FileRow[]
  return rows.map(toFileRecord)
}

/** 无条件删除元数据行（不做任何实体/历史引用扫描） */
export function deleteFile(id: string, db: Database.Database = getDatabase()): boolean {
  const result = db.prepare('DELETE FROM files WHERE id = ?').run(id)
  return result.changes > 0
}

function findFileRow(db: Database.Database, id: string): FileRow | undefined {
  return db.prepare('SELECT * FROM files WHERE id = ?').get(id) as FileRow | undefined
}

function toFileRecord(row: FileRow): FileRecord {
  return {
    id: row.id,
    original_name: row.original_name,
    media_type: row.media_type,
    module: row.module,
    size: row.size,
    sha256: row.sha256,
    uploaded_by: row.uploaded_by,
    created_at: row.created_at,
  }
}
