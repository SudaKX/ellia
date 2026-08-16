import type { PresenceUser } from '@ellia/puzzle-schema'

import type { RoomMember } from './rooms.js'

interface FocusRecord {
  connectionId: string
  userId: string
  username: string
  entityId: string
  dataPath?: string
  updatedAt: string
}

const focusByConnection = new Map<string, FocusRecord>()

export function setFocus(
  connectionId: string,
  userId: string,
  username: string,
  entityId: string,
  dataPath?: string,
): void {
  focusByConnection.set(connectionId, {
    connectionId,
    userId,
    username,
    entityId,
    dataPath,
    updatedAt: new Date().toISOString(),
  })
}

export function clearFocus(connectionId: string): void {
  focusByConnection.delete(connectionId)
}

/** 按房间成员聚合 presence：同用户多连接取最近一次 focus */
export function buildPresence(members: RoomMember[]): PresenceUser[] {
  const byUser = new Map<string, PresenceUser & { updatedAt?: string }>()
  for (const member of members) {
    const focus = focusByConnection.get(member.connectionId)
    if (!focus) {
      if (!byUser.has(member.userId)) {
        byUser.set(member.userId, { id: member.userId, username: member.username })
      }
      continue
    }
    const previous = byUser.get(focus.userId)
    if (!previous || !previous.updatedAt || focus.updatedAt > previous.updatedAt) {
      byUser.set(focus.userId, {
        id: focus.userId,
        username: focus.username,
        entity_id: focus.entityId,
        data_path: focus.dataPath,
        updatedAt: focus.updatedAt,
      })
    }
  }
  const users = [...byUser.values()]
    .sort((a, b) => a.username.localeCompare(b.username))
    .map(({ updatedAt: _updatedAt, ...user }) => user)
  return users
}
