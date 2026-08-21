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
  {
    version: 2,
    up(db) {
      db.exec(`
        CREATE TABLE projects (
          id              TEXT PRIMARY KEY,
          module_id       TEXT NOT NULL UNIQUE COLLATE NOCASE,
          display_name    TEXT NOT NULL,
          description     TEXT,
          deploy_baseline TEXT,
          created_by      TEXT NOT NULL REFERENCES users(id),
          created_at      TEXT NOT NULL,
          updated_at      TEXT NOT NULL
        );

        CREATE INDEX idx_projects_updated_at ON projects(updated_at DESC);
      `)
    },
  },
  {
    version: 3,
    up(db) {
      db.exec(`
        CREATE TABLE entities (
          id          TEXT PRIMARY KEY,
          project_id  TEXT NOT NULL REFERENCES projects(id),
          "group"     TEXT NOT NULL,
          kind        TEXT NOT NULL,
          ui_kind     TEXT NOT NULL,
          resource_id TEXT NOT NULL,
          revision    INTEGER NOT NULL,
          version     INTEGER NOT NULL,
          state       TEXT NOT NULL,
          created_at  TEXT NOT NULL,
          updated_at  TEXT NOT NULL
        );

        CREATE UNIQUE INDEX idx_entities_resource
          ON entities(project_id, resource_id);
        CREATE INDEX idx_entities_group ON entities(project_id, "group", kind);

        CREATE TABLE entity_history (
          id         INTEGER PRIMARY KEY AUTOINCREMENT,
          entity_id  TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
          version    INTEGER NOT NULL,
          state      TEXT NOT NULL,
          author_id  TEXT NOT NULL REFERENCES users(id),
          created_at TEXT NOT NULL,
          UNIQUE(entity_id, version)
        );

        CREATE INDEX idx_entity_history ON entity_history(entity_id, version DESC);

        CREATE TABLE files (
          id            TEXT PRIMARY KEY,
          original_name TEXT,
          media_type    TEXT NOT NULL,
          size          INTEGER NOT NULL,
          sha256        TEXT NOT NULL,
          uploaded_by   TEXT NOT NULL REFERENCES users(id),
          created_at    TEXT NOT NULL
        );

        CREATE TABLE app_meta (
          "key" TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
      `)
    },
  },
  {
    version: 4,
    up(db) {
      db.exec(`
        CREATE TABLE voice_channels (
          id               TEXT PRIMARY KEY,
          project_id       TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          name             TEXT NOT NULL COLLATE NOCASE,
          max_participants INTEGER NOT NULL DEFAULT 8
                           CHECK (max_participants > 0 AND max_participants <= 8),
          created_by       TEXT NOT NULL REFERENCES users(id),
          created_at       TEXT NOT NULL,
          updated_at       TEXT NOT NULL,
          UNIQUE (project_id, name)
        );

        CREATE INDEX idx_voice_channels_project
          ON voice_channels(project_id);
      `)
    },
  },
  {
    version: 5,
    up(db) {
      db.exec(`
        ALTER TABLE entities ADD COLUMN comment TEXT NOT NULL DEFAULT '';
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
