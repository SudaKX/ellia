export interface LockHolder {
  connectionId: string
  userId: string
  username: string
  acquiredAt: string
}

export type LockAttempt =
  | { ok: true; replacedKeys: string[] }
  | { ok: false; holder: LockHolder }

const locks = new Map<string, LockHolder>()
const locksByConnection = new Map<string, Set<string>>()

/**
 * 获取字段锁。同连接同路径幂等；同连接新路径自动顶替旧锁；
 * 其他连接持有时返回 holder。
 */
export function tryLock(
  connectionId: string,
  userId: string,
  username: string,
  lockKey: string,
): LockAttempt {
  const existing = locks.get(lockKey)
  if (existing && existing.connectionId !== connectionId) {
    return { ok: false, holder: existing }
  }
  if (existing) return { ok: true, replacedKeys: [] }

  const replacedKeys = releaseByConnection(connectionId)
  locks.set(lockKey, {
    connectionId,
    userId,
    username,
    acquiredAt: new Date().toISOString(),
  })
  let owned = locksByConnection.get(connectionId)
  if (!owned) {
    owned = new Set()
    locksByConnection.set(connectionId, owned)
  }
  owned.add(lockKey)
  return { ok: true, replacedKeys }
}

export function releaseLock(lockKey: string): LockHolder | undefined {
  const holder = locks.get(lockKey)
  if (!holder) return undefined
  locks.delete(lockKey)
  locksByConnection.get(holder.connectionId)?.delete(lockKey)
  return holder
}

/** 断开/顶替时释放某连接全部锁，返回被释放的锁键列表 */
export function releaseByConnection(connectionId: string): string[] {
  const owned = locksByConnection.get(connectionId)
  if (!owned) return []
  const keys = [...owned]
  for (const key of keys) {
    const holder = locks.get(key)
    if (holder?.connectionId === connectionId) locks.delete(key)
  }
  locksByConnection.delete(connectionId)
  return keys
}

export function getLock(lockKey: string): LockHolder | undefined {
  return locks.get(lockKey)
}

/** 其他连接是否持有该实体任意字段锁（锁键前缀 `<entity_id>@`） */
export function findEntityLockHolder(
  entityId: string,
  exceptConnectionId: string,
): LockHolder | undefined {
  const prefix = `${entityId}@`
  for (const [key, holder] of locks) {
    if (key.startsWith(prefix) && holder.connectionId !== exceptConnectionId) return holder
  }
  return undefined
}

export function locksOfEntity(entityId: string): string[] {
  const prefix = `${entityId}@`
  return [...locks.keys()].filter((key) => key.startsWith(prefix))
}
