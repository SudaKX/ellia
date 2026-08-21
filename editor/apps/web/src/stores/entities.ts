import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import type {
  DeletedMessage,
  EntityId,
  EntityRecord,
  RolledBackMessage,
  ServerMessage,
  SyncMessage,
  UpdateMessage,
} from '@ellia/puzzle-schema'
import { parseDataPath } from '@ellia/puzzle-schema'

import { syncClient } from '../client/ws'

const ENTITY_STORAGE_PREFIX = 'ellia:entities:'

function storageKey(projectId: string): string {
  return `${ENTITY_STORAGE_PREFIX}${projectId}`
}

function readStoredEntities(projectId: string): Record<EntityId, EntityRecord> {
  try {
    const raw = localStorage.getItem(storageKey(projectId))
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, unknown>
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return {}
    return parsed as Record<EntityId, EntityRecord>
  } catch {
    return {}
  }
}

export const useEntitiesStore = defineStore('entities', () => {
  const projectId = ref<string | null>(null)
  const entities = ref<Record<EntityId, EntityRecord>>({})
  const deletedEntityIds = ref<Set<EntityId>>(new Set())
  const lastSyncAt = ref<number | null>(null)

  let saveTimer: ReturnType<typeof setTimeout> | null = null
  let subscriptionsReady = false

  const entityList = computed(() => Object.values(entities.value))
  const vector = computed(() =>
    Object.fromEntries(Object.values(entities.value).map((entry) => [entry.id, entry.revision])),
  )

  function initialize(nextProjectId: string): void {
    if (projectId.value !== nextProjectId) {
      projectId.value = nextProjectId
      entities.value = readStoredEntities(nextProjectId)
      deletedEntityIds.value = new Set()
      lastSyncAt.value = null
    }
    ensureSubscriptions()
  }

  function clear(): void {
    projectId.value = null
    entities.value = {}
    deletedEntityIds.value = new Set()
    lastSyncAt.value = null
  }

  function replaceFromSync(message: SyncMessage): void {
    // sync 是增量协议：只包含缺失或 revision 不一致的实体，以及已删除的 id。
    // 必须保留本地已经与服务端一致的实体，否则空 sync 会清空整个实体列表。
    const next = { ...entities.value }
    for (const entity of message.entities) next[entity.id] = entity
    for (const id of message.removed_ids) delete next[id]
    entities.value = next
    lastSyncAt.value = Date.now()
    scheduleSave()
  }

  function upsertEntity(entity: EntityRecord): void {
    entities.value = { ...entities.value, [entity.id]: entity }
    lastSyncAt.value = Date.now()
    scheduleSave()
  }

  function applyUpdate(message: UpdateMessage): void {
    const entity = entities.value[message.entity_id]
    if (!entity) return
    const parsed = parseDataPath(message.data_path, message.entity_id)
    if (!parsed) return

    const nextEntity: EntityRecord = {
      ...entity,
      revision: message.revision,
      version: message.version,
      state: { ...entity.state },
    }
    if (parsed.root === 'state') {
      const stateRoot = nextEntity.state as unknown as Record<string, unknown>
      nextEntity.state = (
        message.op === 'remove'
          ? removePointerValue(stateRoot, parsed.json_path)
          : setPointerValue(stateRoot, parsed.json_path, message.value)
      ) as unknown as EntityRecord['state']
    } else if (parsed.root === 'group') {
      nextEntity.group = message.value as string
    } else if (parsed.root === 'resource_id') {
      nextEntity.resource_id = message.value as string
    } else if (parsed.root === 'comment') {
      nextEntity.comment = message.value as string
    }
    entities.value = { ...entities.value, [nextEntity.id]: nextEntity }
    lastSyncAt.value = Date.now()
    scheduleSave()
  }

  function applyRolledBack(message: RolledBackMessage): void {
    const entity = entities.value[message.entity_id]
    if (!entity) return
    entities.value = {
      ...entities.value,
      [message.entity_id]: {
        ...entity,
        revision: message.revision,
        version: message.version,
        state: message.state,
      },
    }
    lastSyncAt.value = Date.now()
    scheduleSave()
  }

  function applyDeleted(message: DeletedMessage): void {
    const next = { ...entities.value }
    delete next[message.entity_id]
    entities.value = next
    // 记录被删除的实体 id（用于 UI 提示）
    deletedEntityIds.value = new Set(deletedEntityIds.value).add(message.entity_id)
    lastSyncAt.value = Date.now()
    scheduleSave()
  }

  function scheduleSave(): void {
    if (!projectId.value) return
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(() => {
      try {
        localStorage.setItem(storageKey(projectId.value!), JSON.stringify(entities.value))
      } catch (error) {
        console.warn('[entities] localStorage 写入失败：', error)
      }
      saveTimer = null
    }, 500)
  }

  function ensureSubscriptions(): void {
    if (subscriptionsReady) return
    subscriptionsReady = true
    syncClient.on('sync', (message) => replaceFromSync(message))
    syncClient.on('created', (message) => {
      if (message.entity) upsertEntity(message.entity)
    })
    syncClient.on('update', (message) => applyUpdate(message))
    syncClient.on('rolled_back', (message) => applyRolledBack(message))
    syncClient.on('deleted', (message) => applyDeleted(message))
  }

  return {
    projectId,
    entities,
    deletedEntityIds,
    lastSyncAt,
    entityList,
    vector,
    initialize,
    clear,
    replaceFromSync,
    upsertEntity,
    applyUpdate,
    applyRolledBack,
    applyDeleted,
  }
})

function setPointerValue(
  target: Record<string, unknown>,
  pointer: string,
  value: unknown,
): Record<string, unknown> {
  if (pointer === '') return value as Record<string, unknown>

  const tokens = pointer
    .replace(/^\//, '')
    .split('/')
    .map((token) => token.replace(/~1/g, '/').replace(/~0/g, '~'))

  let current: Record<string, unknown> = target
  for (let index = 0; index < tokens.length - 1; index += 1) {
    const key = tokens[index] ?? ''
    const child = current[key]
    if (child === undefined || child === null || typeof child !== 'object' || Array.isArray(child)) {
      current[key] = {}
    }
    current = current[key] as Record<string, unknown>
  }
  const lastKey = tokens[tokens.length - 1] ?? ''
  current[lastKey] = value
  return target
}

function removePointerValue(
  target: Record<string, unknown>,
  pointer: string,
): Record<string, unknown> {
  if (pointer === '') return target

  const tokens = pointer
    .replace(/^\//, '')
    .split('/')
    .map((token) => token.replace(/~1/g, '/').replace(/~0/g, '~'))

  let current: unknown = target
  for (let index = 0; index < tokens.length - 1; index += 1) {
    const key = tokens[index] ?? ''
    if (Array.isArray(current)) {
      const position = Number(key)
      if (!Number.isInteger(position) || position < 0 || position >= current.length) return target
      current = current[position]
      continue
    }
    if (typeof current !== 'object' || current === null || !(key in current)) return target
    current = (current as Record<string, unknown>)[key]
  }
  const lastKey = tokens[tokens.length - 1] ?? ''
  if (Array.isArray(current)) {
    const position = Number(lastKey)
    if (!Number.isInteger(position) || position < 0 || position >= current.length) return target
    current.splice(position, 1)
  } else if (typeof current === 'object' && current !== null && lastKey in current) {
    delete (current as Record<string, unknown>)[lastKey]
  }
  return target
}