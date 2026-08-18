// @ellia/puzzle-schema — WS v2 同步协议消息（plan-v2 §6）
// 模型：后端权威状态；revision 单调同步锚点；字段锁保护增量 patch；
// 重连按 revision 向量全量同步（无增量重放）。

import type { EntityId, EntityKind, EntityRecord, EntityState, UiKind } from './types.js'

export const SYNC_PROTOCOL_VERSION = 2

export interface AuthorInfo {
  id: string
  username: string
}

export interface PresenceUser {
  id: string
  username: string
  entity_id?: EntityId
  data_path?: string
}

export interface HistoryEntry {
  version: number
  state: EntityState
  author_id: string
  created_at: string
}

// ---------- C → S ----------

export interface JoinMessage {
  type: 'join'
  project_id: string
  /** entity_id → revision 的本地版本向量 */
  vector: Record<EntityId, number>
}

export interface CreateMessage {
  type: 'create'
  /** 提交者自定 ref（用于响应匹配） */
  ref: string
  group: string
  kind: EntityKind
  /** 必填：前端展示类型，服务端校验 kind 允许值 */
  ui_kind: UiKind
  /** 完整 resource_id：<namespace>:<id> */
  resource_id: string
  state: EntityState
}

export interface PatchMessage {
  type: 'patch'
  ref: string
  entity_id: EntityId
  /** 已由 lock 建立的锁路径：<entity_id>@<root>:<json_path> */
  data_path: string
  value: unknown
}

export interface DeleteMessage {
  type: 'delete'
  ref: string
  entity_id: EntityId
}

export interface RollbackMessage {
  type: 'rollback'
  ref: string
  entity_id: EntityId
}

export interface HistoryRequestMessage {
  type: 'history'
  ref: string
  entity_id: EntityId
}

export interface LockMessage {
  type: 'lock'
  ref: string
  entity_id: EntityId
  data_path: string
}

export interface UnlockMessage {
  type: 'unlock'
  ref?: string
  entity_id: EntityId
  data_path: string
}

export interface FocusMessage {
  type: 'focus'
  /** null 表示清除当前连接记录的用户焦点 */
  entity_id: EntityId | null
  data_path?: string
}

export interface PingMessage {
  type: 'ping'
}

export type ClientMessage =
  | JoinMessage
  | CreateMessage
  | PatchMessage
  | DeleteMessage
  | RollbackMessage
  | HistoryRequestMessage
  | LockMessage
  | UnlockMessage
  | FocusMessage
  | PingMessage

// ---------- S → C ----------

export interface HelloMessage {
  type: 'hello'
  service: string
  protocol_version: number
}

export interface SyncMessage {
  type: 'sync'
  /** revision 与向量不一致或客户端缺失的实体（全量状态） */
  entities: EntityRecord[]
  /** 向量中有、DB 中已不存在的实体 id（含物理删除） */
  removed_ids: EntityId[]
}

export interface CreatedMessage {
  type: 'created'
  /** 仅提交者使用；广播时其他客户端忽略 */
  ref?: string
  entity: EntityRecord
}

export interface AppliedMessage {
  type: 'applied'
  ref: string
  entity_id: EntityId
  revision: number
  version: number
}

export interface UpdateMessage {
  type: 'update'
  entity_id: EntityId
  revision: number
  version: number
  data_path: string
  value: unknown
  author: AuthorInfo
}

export interface DeletedMessage {
  type: 'deleted'
  ref?: string
  entity_id: EntityId
}

export interface RolledBackMessage {
  type: 'rolled_back'
  ref?: string
  entity_id: EntityId
  revision: number
  version: number
  state: EntityState
  author: AuthorInfo
}

export interface HistoryResponseMessage {
  type: 'history'
  ref: string
  entity_id: EntityId
  entries: HistoryEntry[]
}

export interface LockedMessage {
  type: 'locked'
  ref?: string
  entity_id: EntityId
  data_path: string
  user?: AuthorInfo
}

export interface UnlockedMessage {
  type: 'unlocked'
  ref?: string
  entity_id: EntityId
  data_path: string
  user?: AuthorInfo
}

export interface LockDeniedMessage {
  type: 'lock_denied'
  ref: string
  entity_id: EntityId
  data_path: string
  holder: AuthorInfo
}

export interface PresenceMessage {
  type: 'presence'
  users: PresenceUser[]
}

export interface LocksMessage {
  type: 'locks'
  locks: Array<{
    data_path: string
    holder: AuthorInfo
  }>
}

export interface ErrorMessage {
  type: 'error'
  ref?: string
  code: string
  message: string
}

export interface PongMessage {
  type: 'pong'
}

export type ServerMessage =
  | HelloMessage
  | SyncMessage
  | CreatedMessage
  | AppliedMessage
  | UpdateMessage
  | DeletedMessage
  | RolledBackMessage
  | HistoryResponseMessage
  | LockedMessage
  | UnlockedMessage
  | LockDeniedMessage
  | PresenceMessage
  | LocksMessage
  | ErrorMessage
  | PongMessage
