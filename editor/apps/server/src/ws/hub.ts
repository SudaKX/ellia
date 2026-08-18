import { randomUUID } from 'node:crypto'
import type { Server as HttpServer, IncomingMessage } from 'node:http'
import type { Duplex } from 'node:stream'

import {
  SYNC_PROTOCOL_VERSION,
  parseDataPath,
  type ClientMessage,
  type ServerMessage,
} from '@ellia/puzzle-schema'
import { WebSocketServer, WebSocket } from 'ws'

import { findSessionWithUser, parseSessionCookie } from '../auth/sessions.js'
import { getDatabase } from '../db/database.js'
import { ApiError } from '../errors.js'
import { findProjectById } from '../services/projects.js'
import {
  createEntity,
  deleteEntity,
  listHistory,
  listProjectEntities,
  patchEntity,
  requireEntity,
  rollbackEntity,
  toEntityRecord,
} from '../services/entities.js'
import {
  findEntityLockHolder,
  getLock,
  listLocks,
  locksOfEntity,
  releaseByConnection,
  releaseLock,
  tryLock,
} from './locks.js'
import { buildPresence, clearFocus, setFocus } from './presence.js'
import { broadcastRoom, joinRoom, leaveRoom, listRoom } from './rooms.js'

/** WS 端点前缀：/ws/projects/:id（cookie 会话认证） */
export const WS_PATH_PREFIX = '/ws'

const HEARTBEAT_INTERVAL_MS = 30_000

interface ConnectionContext {
  connectionId: string
  projectId: string
  userId: string
  username: string
  isAlive: boolean
}

const contexts = new Map<WebSocket, ConnectionContext>()

export function attachWebSocketHub(server: HttpServer): WebSocketServer {
  const wss = new WebSocketServer({ noServer: true })

  server.on('upgrade', (request, socket, head) => {
    const url = new URL(request.url ?? '/', 'http://localhost')
    const match = url.pathname.match(/^\/ws\/projects\/([^/]+)$/)
    if (!match) return

    let projectId: string
    try {
      projectId = decodeURIComponent(match[1] ?? '')
    } catch {
      rejectUpgrade(socket, 400, 'Bad Request')
      return
    }
    if (!projectId) {
      rejectUpgrade(socket, 400, 'Bad Request')
      return
    }

    const token = parseSessionCookie(request.headers.cookie ?? '')
    const session = token ? findSessionWithUser(getDatabase(), token) : undefined
    if (!session) {
      rejectUpgrade(socket, 401, 'Unauthorized')
      return
    }
    if (!findProjectById(projectId)) {
      rejectUpgrade(socket, 404, 'Project not found')
      return
    }

    const context: ConnectionContext = {
      connectionId: randomUUID(),
      projectId,
      userId: session.user.id,
      username: session.user.username,
      isAlive: true,
    }
    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit('connection', ws, request, context)
    })
  })

  wss.on('connection', (ws: WebSocket, _request: IncomingMessage, context: ConnectionContext) => {
    contexts.set(ws, context)
    joinRoom(context.projectId, {
      connectionId: context.connectionId,
      userId: context.userId,
      username: context.username,
      ws,
    })

    send(ws, { type: 'hello', service: 'ellia-server', protocol_version: SYNC_PROTOCOL_VERSION })
    broadcastPresence(context.projectId)

    const heartbeat = setInterval(() => {
      if (!context.isAlive) {
        ws.terminate()
        return
      }
      context.isAlive = false
    }, HEARTBEAT_INTERVAL_MS)

    ws.on('message', (data) => {
      context.isAlive = true
      let message: ClientMessage
      try {
        message = JSON.parse(data.toString()) as ClientMessage
      } catch {
        sendError(ws, 'BAD_JSON', '消息不是合法 JSON')
        return
      }
      handleMessage(ws, context, message)
    })

    ws.on('close', () => {
      clearInterval(heartbeat)
      const released = releaseByConnection(context.connectionId)
      for (const key of released) {
        broadcastRoom(context.projectId, { type: 'unlocked', entity_id: key.split('@')[0] ?? '', data_path: key })
      }
      leaveRoom(context.projectId, context.connectionId)
      contexts.delete(ws)
      broadcastPresence(context.projectId)
    })

    ws.on('error', () => {
      // close 事件负责清理
    })
  })

  return wss
}

function handleMessage(ws: WebSocket, context: ConnectionContext, message: ClientMessage): void {
  switch (message.type) {
    case 'ping':
      send(ws, { type: 'pong' })
      return
    case 'join':
      handleJoin(ws, context, message.project_id, message.vector)
      return
    case 'create':
      handleCreate(ws, context, message)
      return
    case 'lock':
      handleLock(ws, context, message.ref, message.entity_id, message.data_path)
      return
    case 'unlock':
      handleUnlock(ws, context, message.ref, message.entity_id, message.data_path)
      return
    case 'patch':
      handlePatch(ws, context, message.ref, message.entity_id, message.data_path, message.value)
      return
    case 'delete':
      handleDelete(ws, context, message.ref, message.entity_id)
      return
    case 'rollback':
      handleRollback(ws, context, message.ref, message.entity_id)
      return
    case 'history':
      handleHistory(ws, context, message.ref, message.entity_id)
      return
    case 'focus':
      handleFocus(ws, context, message.entity_id, message.data_path)
      return
    default:
      sendError(ws, 'VALIDATION', `未知消息类型: ${String((message as { type?: string }).type)}`)
  }
}

function handleJoin(
  ws: WebSocket,
  context: ConnectionContext,
  projectId: string,
  vector: Record<string, number>,
): void {
  if (projectId !== context.projectId) {
    sendError(ws, 'VALIDATION', 'join.project_id 与连接的项目不一致')
    return
  }
  if (
    typeof vector !== 'object' ||
    vector === null ||
    Array.isArray(vector) ||
    Object.values(vector).some((value) => !Number.isInteger(value))
  ) {
    sendError(ws, 'VALIDATION', 'join.vector 必须是 {entity_id: revision}')
    return
  }

  const entities = listProjectEntities(context.projectId)
  const byId = new Map(entities.map((entity) => [entity.id, entity]))
  const payloadEntities = entities
    .filter((entity) => vector[entity.id] !== entity.revision)
    .map(toEntityRecord)
  const removedIds = Object.keys(vector).filter((id) => !byId.has(id))

  send(ws, { type: 'sync', entities: payloadEntities, removed_ids: removedIds })

  const entityIds = new Set(entities.map((entity) => entity.id))
  const projectLocks = listLocks()
    .filter(({ dataPath }) => entityIds.has(dataPath.split('@')[0] ?? ''))
    .map(({ dataPath, holder }) => ({
      data_path: dataPath,
      holder: { id: holder.userId, username: holder.username },
    }))
  send(ws, { type: 'locks', locks: projectLocks })
}

function handleCreate(ws: WebSocket, context: ConnectionContext, message: Extract<ClientMessage, { type: 'create' }>): void {
  try {
    const entity = createEntity(
      context.projectId,
      {
        group: message.group,
        kind: message.kind,
        ui_kind: message.ui_kind,
        resource_id: message.resource_id,
        state: message.state,
      },
      context.userId,
    )
    const record = toEntityRecord(entity)
    send(ws, { type: 'created', ref: message.ref, entity: record })
    broadcastRoom(context.projectId, { type: 'created', entity: record }, context.connectionId)
  } catch (error) {
    sendApiError(ws, error, message.ref)
  }
}

function handleLock(
  ws: WebSocket,
  context: ConnectionContext,
  ref: string,
  entityId: string,
  dataPath: string,
): void {
  try {
    requireEntity(context.projectId, entityId)
    if (!parseDataPath(dataPath, entityId)) {
      sendError(ws, 'VALIDATION', 'data_path 非法', ref)
      return
    }
    const attempt = tryLock(context.connectionId, context.userId, context.username, dataPath)
    if (!attempt.ok) {
      send(ws, {
        type: 'lock_denied',
        ref,
        entity_id: entityId,
        data_path: dataPath,
        holder: { id: attempt.holder.userId, username: attempt.holder.username },
      })
      return
    }
    for (const replaced of attempt.replacedKeys) {
      broadcastRoom(context.projectId, { type: 'unlocked', entity_id: entityId, data_path: replaced })
    }
    broadcastRoom(context.projectId, {
      type: 'locked',
      ref,
      entity_id: entityId,
      data_path: dataPath,
      user: { id: context.userId, username: context.username },
    })
  } catch (error) {
    sendApiError(ws, error, ref)
  }
}

function handleUnlock(
  ws: WebSocket,
  context: ConnectionContext,
  ref: string | undefined,
  entityId: string,
  dataPath: string,
): void {
  const holder = getLock(dataPath)
  if (holder?.connectionId !== context.connectionId) return
  releaseLock(dataPath)
  broadcastRoom(context.projectId, { type: 'unlocked', ref, entity_id: entityId, data_path: dataPath })
}

function handlePatch(
  ws: WebSocket,
  context: ConnectionContext,
  ref: string,
  entityId: string,
  dataPath: string,
  value: unknown,
): void {
  try {
    requireEntity(context.projectId, entityId)
    const holder = getLock(dataPath)
    if (!holder || holder.connectionId !== context.connectionId) {
      sendError(ws, 'STALE_LOCK', '未持有该字段锁，不能提交修改', ref)
      return
    }
    const entity = patchEntity(context.projectId, entityId, dataPath, value, context.userId)
    send(ws, {
      type: 'applied',
      ref,
      entity_id: entityId,
      revision: entity.revision,
      version: entity.version,
    })
    broadcastRoom(context.projectId, {
      type: 'update',
      entity_id: entityId,
      revision: entity.revision,
      version: entity.version,
      data_path: dataPath,
      value,
      author: { id: context.userId, username: context.username },
    })
    releaseLock(dataPath)
    broadcastRoom(context.projectId, { type: 'unlocked', entity_id: entityId, data_path: dataPath })
  } catch (error) {
    if (getLock(dataPath)?.connectionId === context.connectionId) {
      releaseLock(dataPath)
      broadcastRoom(context.projectId, { type: 'unlocked', entity_id: entityId, data_path: dataPath })
    }
    sendApiError(ws, error, ref)
  }
}

function handleDelete(ws: WebSocket, context: ConnectionContext, ref: string, entityId: string): void {
  try {
    requireEntity(context.projectId, entityId)
    const holder = findEntityLockHolder(entityId, context.connectionId)
    if (holder) {
      sendError(
        ws,
        'ENTITY_LOCKED',
        `实体正被 ${holder.username} 编辑，不能删除`,
        ref,
      )
      return
    }
    deleteEntity(context.projectId, entityId)
    for (const key of locksOfEntity(entityId)) {
      releaseLock(key)
      broadcastRoom(context.projectId, { type: 'unlocked', entity_id: entityId, data_path: key })
    }
    broadcastRoom(context.projectId, { type: 'deleted', ref, entity_id: entityId })
  } catch (error) {
    sendApiError(ws, error, ref)
  }
}

function handleRollback(ws: WebSocket, context: ConnectionContext, ref: string, entityId: string): void {
  try {
    requireEntity(context.projectId, entityId)
    const holder = findEntityLockHolder(entityId, context.connectionId)
    if (holder) {
      sendError(
        ws,
        'ENTITY_LOCKED',
        `实体正被 ${holder.username} 编辑，不能回退`,
        ref,
      )
      return
    }
    const entity = rollbackEntity(context.projectId, entityId, context.userId)
    broadcastRoom(context.projectId, {
      type: 'rolled_back',
      ref,
      entity_id: entityId,
      revision: entity.revision,
      version: entity.version,
      state: entity.state,
      author: { id: context.userId, username: context.username },
    })
  } catch (error) {
    sendApiError(ws, error, ref)
  }
}

function handleHistory(ws: WebSocket, context: ConnectionContext, ref: string, entityId: string): void {
  try {
    requireEntity(context.projectId, entityId)
    const entries = listHistory(context.projectId, entityId)
    send(ws, { type: 'history', ref, entity_id: entityId, entries })
  } catch (error) {
    sendApiError(ws, error, ref)
  }
}

function handleFocus(
  ws: WebSocket,
  context: ConnectionContext,
  entityId: string | null,
  dataPath: string | undefined,
): void {
  if (entityId === null) {
    clearFocus(context.connectionId)
    broadcastPresence(context.projectId)
    return
  }
  try {
    requireEntity(context.projectId, entityId)
    if (dataPath !== undefined && !parseDataPath(dataPath, entityId)) {
      sendError(ws, 'VALIDATION', 'focus.data_path 非法')
      return
    }
    setFocus(context.connectionId, context.userId, context.username, entityId, dataPath)
    broadcastPresence(context.projectId)
  } catch (error) {
    sendApiError(ws, error)
  }
}

function broadcastPresence(projectId: string): void {
  const members = listRoom(projectId)
  const users = buildPresence(members)
  broadcastRoom(projectId, { type: 'presence', users })
}

function sendApiError(ws: WebSocket, error: unknown, ref?: string): void {
  if (error instanceof ApiError) {
    send(ws, { type: 'error', ref, code: error.code, message: error.message })
    return
  }
  console.error('[ellia-server] ws handler error:', error)
  send(ws, { type: 'error', ref, code: 'INTERNAL', message: 'Internal server error' })
}

function sendError(ws: WebSocket, code: string, message: string, ref?: string): void {
  send(ws, { type: 'error', ref, code, message })
}

function send(ws: WebSocket, message: ServerMessage): void {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message))
  }
}

function rejectUpgrade(socket: Duplex, status: number, message: string): void {
  const body = `${message}\n`
  socket.write(
    `HTTP/1.1 ${status} ${status === 401 ? 'Unauthorized' : status === 404 ? 'Not Found' : 'Bad Request'}\r\n` +
      'Connection: close\r\n' +
      'Content-Type: text/plain; charset=utf-8\r\n' +
      `Content-Length: ${Buffer.byteLength(body)}\r\n\r\n${body}`,
  )
  socket.destroy()
}
