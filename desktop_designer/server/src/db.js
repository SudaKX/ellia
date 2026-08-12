/**
 * 数据库层：基于 Node 内置 SQLite（node:sqlite，Node 22.5+ / 24 可用），零外部依赖。
 *
 * - 数据文件：server/data/questions.db（自动创建目录）
 * - 表结构：users（含 role）、questions（含生命周期状态）
 * - 全部为同步 API（DatabaseSync），适合本项目的低并发规模
 */

import { DatabaseSync } from 'node:sqlite'
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const DATA_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'data')
mkdirSync(DATA_DIR, { recursive: true })

export const db = new DatabaseSync(join(DATA_DIR, 'questions.db'))

// 开启 WAL 提升并发读性能，并让数据文件更易备份
db.exec('PRAGMA journal_mode = WAL')

db.exec(`
CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('author', 'admin')),
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
  id           TEXT PRIMARY KEY,
  author_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title        TEXT NOT NULL,
  blocks       TEXT NOT NULL DEFAULT '[]',
  type         TEXT NOT NULL CHECK (type IN ('single', 'multi', 'fill')),
  options      TEXT,
  fill_answers TEXT,
  hints        TEXT,
  explanation  TEXT,
  wrong_feedback TEXT,
  status       TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'pending', 'approved', 'rejected')),
  review_note  TEXT,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  published_at TEXT
);
`)

// 兼容旧库：为已存在的 questions 表补充新增列（CREATE TABLE IF NOT EXISTS 不会加列）
const questionColumns = db.prepare("PRAGMA table_info(questions)").all()
if (!questionColumns.some((column) => column.name === 'wrong_feedback')) {
  db.exec('ALTER TABLE questions ADD COLUMN wrong_feedback TEXT')
}
