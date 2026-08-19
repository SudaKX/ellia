import type {
  ClientMessage,
  CreatedMessage,
  DeletedMessage,
  EntityRecord,
  HistoryEntry,
  LockedMessage,
  LockDeniedMessage,
  PatchOp,
  RolledBackMessage,
  ServerMessage,
  UnlockedMessage,
} from '@ellia/puzzle-schema'

type AnyServerMessage = ServerMessage

type Handler<T extends ServerMessage['type']> = (
  message: Extract<ServerMessage, { type: T }>,
) => void

interface PendingRequest {
  type: ServerMessage['type'] | 'lock_denied'
  resolve: (value: unknown) => void
  reject: (reason: Error) => void
  timer: ReturnType<typeof setTimeout>
}

const REF_TIMEOUT_MS = 10_000

function generateRef(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `ref-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export class SyncClient {
  private socket: WebSocket | null = null
  private pending = new Map<string, PendingRequest>()
  private listeners = new Map<ServerMessage['type'], Set<(message: AnyServerMessage) => void>>()
  private openHandlers = new Set<() => void>()
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private shouldReconnect = false
  private url: string | null = null

  connect(url: string): void {
    this.url = url
    this.shouldReconnect = true
    this.open()
  }

  disconnect(): void {
    this.shouldReconnect = false
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.stopHeartbeat()
    this.socket?.close()
    this.socket = null
  }

  on<T extends ServerMessage['type']>(type: T, handler: Handler<T>): () => void {
    const set = this.listeners.get(type) ?? new Set<(message: AnyServerMessage) => void>()
    set.add(handler as (message: AnyServerMessage) => void)
    this.listeners.set(type, set)
    return () => {
      set.delete(handler as (message: AnyServerMessage) => void)
      if (set.size === 0) this.listeners.delete(type)
    }
  }

  onOpen(handler: () => void): () => void {
    this.openHandlers.add(handler)
    if (this.socket?.readyState === WebSocket.OPEN) handler()
    return () => {
      this.openHandlers.delete(handler)
    }
  }

  send(message: ClientMessage): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket 尚未连接')
    }
    this.socket.send(JSON.stringify(message))
  }

  join(projectId: string, vector: Record<string, number>): void {
    this.send({ type: 'join', project_id: projectId, vector })
  }

  focus(entityId: string | null, dataPath?: string): void {
    // focus 是尽力而为的在场信息；连接未建立或已断开时直接忽略。
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return
    if (entityId === null) {
      this.send({ type: 'focus', entity_id: null })
    } else if (dataPath === undefined) {
      this.send({ type: 'focus', entity_id: entityId })
    } else {
      this.send({ type: 'focus', entity_id: entityId, data_path: dataPath })
    }
  }

  ping(): void {
    this.send({ type: 'ping' })
  }

  create(input: Omit<Extract<ClientMessage, { type: 'create' }>, 'type' | 'ref'>): Promise<EntityRecord> {
    return this.request<CreatedMessage, EntityRecord>(
      {
        type: 'create',
        ...input,
        ref: generateRef(),
      },
      'created',
      (message) => message.entity,
    )
  }

  patch(
    entityId: string,
    dataPath: string,
    value: unknown,
    op: PatchOp = 'set',
  ): Promise<{ revision: number; version: number }> {
    return this.request<Extract<ServerMessage, { type: 'applied' }>, { revision: number; version: number }>(
      {
        type: 'patch',
        ref: generateRef(),
        entity_id: entityId,
        data_path: dataPath,
        op,
        ...(op === 'set' ? { value } : {}),
      },
      'applied',
      (message) => ({ revision: message.revision, version: message.version }),
    )
  }

  removeField(entityId: string, dataPath: string): Promise<{ revision: number; version: number }> {
    return this.patch(entityId, dataPath, undefined, 'remove')
  }

  lock(entityId: string, dataPath: string): Promise<LockedMessage> {
    return this.request<LockedMessage, LockedMessage>(
      { type: 'lock', ref: generateRef(), entity_id: entityId, data_path: dataPath },
      'locked',
      (message) => message,
    )
  }

  unlock(entityId: string, dataPath: string): Promise<UnlockedMessage> {
    return this.request<UnlockedMessage, UnlockedMessage>(
      { type: 'unlock', ref: generateRef(), entity_id: entityId, data_path: dataPath },
      'unlocked',
      (message) => message,
    )
  }

  delete(entityId: string): Promise<DeletedMessage> {
    return this.request<DeletedMessage, DeletedMessage>(
      { type: 'delete', ref: generateRef(), entity_id: entityId },
      'deleted',
      (message) => message,
    )
  }

  rollback(entityId: string): Promise<RolledBackMessage> {
    return this.request<RolledBackMessage, RolledBackMessage>(
      { type: 'rollback', ref: generateRef(), entity_id: entityId },
      'rolled_back',
      (message) => message,
    )
  }

  history(entityId: string): Promise<HistoryEntry[]> {
    return this.request<Extract<ServerMessage, { type: 'history' }>, HistoryEntry[]>(
      { type: 'history', ref: generateRef(), entity_id: entityId },
      'history',
      (message) => message.entries,
    )
  }

  private open(): void {
    if (!this.url) return
    const socket = new WebSocket(this.url)
    this.socket = socket
    socket.onopen = () => {
      this.startHeartbeat()
      this.dispatchOpen()
    }
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(String(event.data)) as ServerMessage
        this.dispatch(message)
        this.settlePending(message)
      } catch {
        // 非 JSON 消息忽略
      }
    }
    socket.onclose = () => {
      this.stopHeartbeat()
      this.socket = null
      if (this.shouldReconnect && this.url) {
        this.reconnectTimer = setTimeout(() => this.open(), 1000)
      }
    }
    socket.onerror = () => {
      socket.close()
    }
  }

  private dispatchOpen(): void {
    for (const handler of [...this.openHandlers]) {
      try {
        handler()
      } catch (error) {
        console.error('[SyncClient] open handler error:', error)
      }
    }
  }

  private dispatch(message: ServerMessage): void {
    const handlers = this.listeners.get(message.type)
    if (!handlers) return
    for (const handler of [...handlers]) {
      try {
        handler(message)
      } catch (error) {
        console.error('[SyncClient] listener error:', error)
      }
    }
  }

  private settlePending(message: ServerMessage): void {
    const ref = (message as { ref?: string }).ref
    if (!ref) return
    const pending = this.pending.get(ref)
    if (!pending) return

    if (message.type === 'error') {
      const error = message as Extract<ServerMessage, { type: 'error' }>
      this.pending.delete(ref)
      clearTimeout(pending.timer)
      pending.reject(new Error(error.message))
      return
    }

    if (message.type === 'lock_denied' && pending.type === 'locked') {
      const denied = message as LockDeniedMessage
      this.pending.delete(ref)
      clearTimeout(pending.timer)
      pending.reject(new Error(`lock_denied by ${denied.holder.username}`))
      return
    }

    if (message.type === pending.type) {
      this.pending.delete(ref)
      clearTimeout(pending.timer)
      pending.resolve(message)
    }
  }

  private request<M extends ServerMessage, R>(
    message: ClientMessage & { ref: string },
    expectedType: M['type'],
    transform: (message: M) => R,
  ): Promise<R> {
    return new Promise<R>((resolve, reject) => {
      const ref = message.ref
      const timer = setTimeout(() => {
        this.pending.delete(ref)
        reject(new Error('WebSocket 请求超时'))
      }, REF_TIMEOUT_MS)
      this.pending.set(ref, {
        type: expectedType,
        resolve: (value) => resolve(transform(value as M)),
        reject,
        timer,
      })
      try {
        this.send(message)
      } catch (error) {
        this.pending.delete(ref)
        clearTimeout(timer)
        reject(error instanceof Error ? error : new Error('WebSocket 发送失败'))
      }
    })
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      try {
        this.ping()
      } catch {
        // 未连接时不发送
      }
    }, 30_000)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }
}