import fs from 'node:fs'
import path from 'node:path'

import Database from 'better-sqlite3'

import { runMigrations } from './migrations.js'

let activeConnection: Database.Database | undefined

/** 打开（或重开）数据库并应用全部迁移；会替换当前进程内的连接。 */
export function initDatabase(dbPath: string): Database.Database {
  closeDatabase()
  const connection = createDatabase(dbPath)
  activeConnection = connection
  return connection
}

/** 创建独立连接（生产与测试共用）；`':memory:'` 用于测试隔离。 */
export function createDatabase(dbPath: string): Database.Database {
  if (dbPath !== ':memory:') {
    fs.mkdirSync(path.dirname(path.resolve(dbPath)), { recursive: true })
  }
  const connection = new Database(dbPath)
  connection.pragma('journal_mode = WAL')
  connection.pragma('foreign_keys = ON')
  runMigrations(connection)
  return connection
}

/** 返回当前进程内的数据库连接（须先 initDatabase）。 */
export function getDatabase(): Database.Database {
  if (!activeConnection) {
    throw new Error('database has not been initialized')
  }
  return activeConnection
}

export function closeDatabase(): void {
  activeConnection?.close()
  activeConnection = undefined
}

export function isSqliteConstraintError(error: unknown): boolean {
  return (
    error instanceof Error &&
    'code' in error &&
    typeof (error as { code?: unknown }).code === 'string' &&
    (error as { code: string }).code.startsWith('SQLITE_CONSTRAINT_')
  )
}
