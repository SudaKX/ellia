import { randomUUID } from 'node:crypto'

import {
  VOICE_DEFAULT_MAX_PARTICIPANTS,
  type VoiceChannelRecord,
} from '@ellia/puzzle-schema'
import type Database from 'better-sqlite3'

import { getDatabase, isSqliteConstraintError } from '../db/database.js'
import { ApiError } from '../errors.js'
import { findProjectById } from '../services/projects.js'

interface VoiceChannelRow {
  id: string
  project_id: string
  name: string
  max_participants: number
  created_by: string
  created_at: string
  updated_at: string
}

export function toVoiceChannelRecord(row: VoiceChannelRow): VoiceChannelRecord {
  return {
    id: row.id,
    project_id: row.project_id,
    name: row.name,
    max_participants: row.max_participants,
    created_by: row.created_by,
    created_at: row.created_at,
    updated_at: row.updated_at,
  }
}

export function requireProject(projectId: string): void {
  if (!findProjectById(projectId)) {
    throw new ApiError(404, 'PROJECT_NOT_FOUND', '项目不存在')
  }
}

export function listVoiceChannels(
  projectId: string,
  db: Database.Database = getDatabase(),
): VoiceChannelRecord[] {
  const rows = db
    .prepare(
      `SELECT * FROM voice_channels
       WHERE project_id = ?
       ORDER BY created_at ASC, id ASC`,
    )
    .all(projectId) as VoiceChannelRow[]
  return rows.map(toVoiceChannelRecord)
}

export function findVoiceChannelById(
  projectId: string,
  channelId: string,
  db: Database.Database = getDatabase(),
): VoiceChannelRecord | undefined {
  const row = db
    .prepare(
      `SELECT * FROM voice_channels
       WHERE id = ? AND project_id = ?`,
    )
    .get(channelId, projectId) as VoiceChannelRow | undefined
  return row ? toVoiceChannelRecord(row) : undefined
}

export function createVoiceChannel(
  projectId: string,
  name: string,
  createdBy: string,
  maxParticipants = VOICE_DEFAULT_MAX_PARTICIPANTS,
  db: Database.Database = getDatabase(),
): VoiceChannelRecord {
  requireProject(projectId)
  const normalizedName = name.trim()
  if (!normalizedName) {
    throw new ApiError(400, 'VALIDATION', '频道名称不能为空')
  }
  if (normalizedName.length > 40) {
    throw new ApiError(400, 'VALIDATION', '频道名称不能超过 40 个字符')
  }
  if (!Number.isInteger(maxParticipants) || maxParticipants < 1 || maxParticipants > 8) {
    throw new ApiError(400, 'VALIDATION', '频道人数上限必须在 1-8 之间')
  }

  const now = new Date().toISOString()
  const id = randomUUID()
  try {
    db.prepare(
      `INSERT INTO voice_channels
         (id, project_id, name, max_participants, created_by, created_at, updated_at)
       VALUES (@id, @project_id, @name, @max_participants, @created_by, @created_at, @updated_at)`,
    ).run({
      id,
      project_id: projectId,
      name: normalizedName,
      max_participants: maxParticipants,
      created_by: createdBy,
      created_at: now,
      updated_at: now,
    })
  } catch (error) {
    if (isSqliteConstraintError(error)) {
      throw new ApiError(409, 'RESOURCE_CONFLICT', '项目内已存在同名频道')
    }
    throw error
  }

  const channel = findVoiceChannelById(projectId, id)
  if (!channel) throw new Error('voice channel insert did not persist')
  return channel
}

export function deleteVoiceChannel(
  projectId: string,
  channelId: string,
  db: Database.Database = getDatabase(),
): VoiceChannelRecord | undefined {
  const channel = findVoiceChannelById(projectId, channelId)
  if (!channel) return undefined
  db.prepare('DELETE FROM voice_channels WHERE id = ?').run(channelId)
  return channel
}
