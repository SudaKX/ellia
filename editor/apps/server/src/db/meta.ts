import type Database from 'better-sqlite3'

import type { ServerConfig } from '../config.js'
import { getDatabase } from './database.js'

export const ENTITY_HISTORY_LIMIT_KEY = 'entity_history_limit'

/**
 * 首次建库时把 env 的 ENTITY_HISTORY_LIMIT 固化进 app_meta；
 * 之后运行时只读 app_meta，修改 .env 不再生效。
 */
export function ensureMetaSeeded(
  config: ServerConfig,
  db: Database.Database = getDatabase(),
): void {
  const existing = db
    .prepare('SELECT value FROM app_meta WHERE "key" = ?')
    .get(ENTITY_HISTORY_LIMIT_KEY) as { value: string } | undefined
  if (!existing) {
    db.prepare('INSERT INTO app_meta ("key", value) VALUES (?, ?)').run(
      ENTITY_HISTORY_LIMIT_KEY,
      String(config.entityHistoryLimit),
    )
  }
}

/** 运行时使用的每实体历史快照上限 N */
export function getEntityHistoryLimit(db: Database.Database = getDatabase()): number {
  const row = db
    .prepare('SELECT value FROM app_meta WHERE "key" = ?')
    .get(ENTITY_HISTORY_LIMIT_KEY) as { value: string } | undefined
  if (!row) {
    throw new Error('app_meta.entity_history_limit has not been seeded')
  }
  const value = Number(row.value)
  if (!Number.isInteger(value) || value < 1) {
    throw new Error(`invalid entity_history_limit in app_meta: ${row.value}`)
  }
  return value
}
