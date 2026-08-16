import { randomUUID } from 'node:crypto'

import type { Project } from '@ellia/puzzle-schema'
import type Database from 'better-sqlite3'

import { getDatabase, isSqliteConstraintError } from '../db/database.js'
import { ApiError } from '../errors.js'

interface ProjectRow {
  id: string
  module_id: string
  display_name: string
  description: string | null
  deploy_baseline: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface CreateProjectInput {
  module_id: string
  display_name: string
  description?: string | null
  deploy_baseline?: string | null
}

export interface UpdateProjectInput {
  display_name?: string
  description?: string | null
  deploy_baseline?: string | null
}

export function toProject(row: ProjectRow): Project {
  return {
    id: row.id,
    module_id: row.module_id,
    display_name: row.display_name,
    description: row.description,
    deploy_baseline: row.deploy_baseline,
    created_by: row.created_by,
    created_at: row.created_at,
    updated_at: row.updated_at,
  }
}

export function createProject(input: CreateProjectInput, createdBy: string): Project {
  const db = getDatabase()
  const now = new Date().toISOString()
  const id = randomUUID()
  try {
    db.prepare(
      `INSERT INTO projects (id, module_id, display_name, description, deploy_baseline, created_by, created_at, updated_at)
       VALUES (@id, @module_id, @display_name, @description, @deploy_baseline, @created_by, @created_at, @updated_at)`,
    ).run({
      id,
      module_id: input.module_id,
      display_name: input.display_name,
      description: input.description ?? null,
      deploy_baseline: input.deploy_baseline ?? null,
      created_by: createdBy,
      created_at: now,
      updated_at: now,
    })
  } catch (error) {
    if (isSqliteConstraintError(error)) {
      throw new ApiError(409, 'RESOURCE_CONFLICT', 'module_id 已被占用')
    }
    throw error
  }
  const project = findProject(db, id)
  if (!project) throw new Error('project insert did not persist')
  return project
}

export function listProjects(db: Database.Database = getDatabase()): Project[] {
  const rows = db
    .prepare('SELECT * FROM projects ORDER BY updated_at DESC, id ASC')
    .all() as ProjectRow[]
  return rows.map(toProject)
}

export function findProjectById(
  id: string,
  db: Database.Database = getDatabase(),
): Project | undefined {
  const row = findProject(db, id)
  return row ? toProject(row) : undefined
}

export function updateProject(
  id: string,
  input: UpdateProjectInput,
  db: Database.Database = getDatabase(),
): Project | undefined {
  const row = findProject(db, id)
  if (!row) return undefined
  const now = new Date().toISOString()
  db.prepare(
    `UPDATE projects
     SET display_name = @display_name,
         description = @description,
         deploy_baseline = @deploy_baseline,
         updated_at = @updated_at
     WHERE id = @id`,
  ).run({
    id,
    display_name: input.display_name !== undefined ? input.display_name : row.display_name,
    description: input.description !== undefined ? input.description : row.description,
    deploy_baseline:
      input.deploy_baseline !== undefined ? input.deploy_baseline : row.deploy_baseline,
    updated_at: now,
  })
  return findProjectById(id, db)
}

function findProject(db: Database.Database, id: string): ProjectRow | undefined {
  return db.prepare('SELECT * FROM projects WHERE id = ?').get(id) as ProjectRow | undefined
}
