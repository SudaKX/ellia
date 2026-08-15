import type Database from 'better-sqlite3'

interface Migration {
  version: number
  up: (db: Database.Database) => void
}

const migrations: Migration[] = [
  {
    version: 1,
    up(db) {
      db.exec(`
        CREATE TABLE users (
          id            TEXT PRIMARY KEY,
          username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
          password_hash TEXT NOT NULL,
          role          TEXT NOT NULL CHECK (role IN ('user', 'admin')),
          created_at    TEXT NOT NULL
        );

        CREATE TABLE invite_codes (
          code       TEXT PRIMARY KEY,
          created_by TEXT NOT NULL REFERENCES users(id),
          expires_at TEXT NOT NULL,
          used_by    TEXT REFERENCES users(id),
          used_at    TEXT
        );

        CREATE TABLE sessions (
          token      TEXT PRIMARY KEY,
          user_id    TEXT NOT NULL REFERENCES users(id),
          created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL
        );

        CREATE INDEX idx_invite_codes_created_by ON invite_codes(created_by);
        CREATE INDEX idx_sessions_user_id ON sessions(user_id);
      `)
    },
  },
]

export function runMigrations(db: Database.Database): void {
  const currentVersion = db.pragma('user_version', { simple: true }) as number
  for (const migration of migrations) {
    if (migration.version <= currentVersion) continue
    db.transaction(() => {
      migration.up(db)
      db.pragma(`user_version = ${migration.version}`)
    })()
  }
}
