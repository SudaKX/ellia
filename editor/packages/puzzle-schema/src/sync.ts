// @ellia/puzzle-schema — WS 同步协议消息（plan-v1.md §4）
// 模型：后端权威状态；实体级版本号 + LWW；补丁双向存储；增量 + 全量三级回退。

import type { Change, EntityId, EntityKind, EntityState } from './types.js'

export const SYNC_PROTOCOL_VERSION = 1

// ---------- C → S ----------

export interface JoinMessage {
  type: 'join'
  project_id: string
  /** entity_id → version 的本地版本向量 */
  vector: Record<EntityId, number>
}

export interface PatchMessage {
  type: 'patch'
  /** 提交者自定 ref（用于 applied 确认匹配） */
  ref: string
  entity_id: EntityId
  base_version: number
  changes: Record<string, Change>
}

export interface PingMessage {
  type: 'ping'
}

export type ClientMessage = JoinMessage | PatchMessage | PingMessage

// ---------- S → C ----------

export interface EntityRecord {
  id: EntityId
  kind: EntityKind
  version: number
  state: EntityState
}

export interface Tombstone {
  id: EntityId
  version: number
}

export interface SyncMessage {
  type: 'sync'
  /** 服务器对 vector 不一致的实体发全量状态；客户端缺失的实体发全量 */
  entities: EntityRecord[]
  tombstones: Tombstone[]
}

export interface AppliedMessage {
  type: 'applied'
  ref: string
  entity_id: EntityId
  version: number
  /** 提交时 base_version 已过期（LWW：仍已应用，提示可能覆盖他人改动） */
  base_mismatch?: boolean
}

export interface UpdateMessage {
  type: 'update'
  entity_id: EntityId
  version: number
  changes: Record<string, Change>
  author: string
  base_mismatch?: boolean
}

export interface PresenceMessage {
  type: 'presence'
  users: Array<{ id: string; username: string }>
}

export interface PongMessage {
  type: 'pong'
}

export interface HelloMessage {
  type: 'hello'
  service: string
}

export interface ErrorMessage {
  type: 'error'
  reason: string
}

export type ServerMessage =
  | SyncMessage
  | AppliedMessage
  | UpdateMessage
  | PresenceMessage
  | PongMessage
  | HelloMessage
  | ErrorMessage
