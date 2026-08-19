import { randomUUID } from 'node:crypto'

import {
  ENTITY_KINDS,
  PYTHON_SLOTS,
  allowedUiKinds,
  isValidGroup,
  isValidResourceIdForKind,
  parseDataPath,
  type Entity,
  type EntityHistoryEntry,
  type EntityKind,
  type EntityRecord,
  type EntityState,
  type KindStateMap,
  type PatchOp,
  type UiKind,
} from '@ellia/puzzle-schema'
import type Database from 'better-sqlite3'

import { getDatabase, isSqliteConstraintError } from '../db/database.js'
import { getEntityHistoryLimit } from '../db/meta.js'
import { ApiError } from '../errors.js'

export interface EntityRow {
  id: string
  project_id: string
  group: string
  kind: EntityKind
  ui_kind: UiKind
  resource_id: string
  revision: number
  version: number
  state: string
  created_at: string
  updated_at: string
}

export interface CreateEntityInput {
  group?: string
  kind: unknown
  ui_kind: unknown
  resource_id: string
  state: unknown
}

export interface PatchResult {
  entity: Entity
  data_path: string
  value: unknown
}

export function toEntity(row: EntityRow): Entity {
  return {
    id: row.id,
    project_id: row.project_id,
    group: row.group,
    kind: row.kind,
    ui_kind: row.ui_kind,
    resource_id: row.resource_id,
    revision: row.revision,
    version: row.version,
    state: JSON.parse(row.state) as KindStateMap[EntityKind],
    created_at: row.created_at,
    updated_at: row.updated_at,
  }
}

export function toEntityRecord(entity: Entity): EntityRecord {
  return {
    id: entity.id,
    group: entity.group,
    kind: entity.kind,
    ui_kind: entity.ui_kind,
    resource_id: entity.resource_id,
    revision: entity.revision,
    version: entity.version,
    state: entity.state,
  }
}

export function assertKind(value: unknown): EntityKind {
  if (typeof value !== 'string' || !(ENTITY_KINDS as readonly string[]).includes(value)) {
    throw new ApiError(400, 'VALIDATION', `kind 必须是 16 种实体种类之一`)
  }
  return value as EntityKind
}

function assertUiKind(kind: EntityKind, value: unknown): UiKind {
  if (typeof value !== 'string' || !allowedUiKinds(kind).includes(value as UiKind)) {
    throw new ApiError(400, 'VALIDATION', `ui_kind 不属于 kind=${kind} 的允许值`)
  }
  return value as UiKind
}

function assertGroup(value: unknown): string {
  if (value === undefined) return 'main'
  if (typeof value !== 'string' || !isValidGroup(value)) {
    throw new ApiError(400, 'VALIDATION', 'group 必须是 Python 模块路径段格式')
  }
  return value
}

function assertResourceId(kind: EntityKind, value: unknown): string {
  if (typeof value !== 'string' || !isValidResourceIdForKind(kind, value)) {
    throw new ApiError(400, 'VALIDATION', `resource_id 格式非法或命名空间与 kind=${kind} 不匹配`)
  }
  return value
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function assertStringArray(value: unknown, field: string): void {
  if (
    !Array.isArray(value) ||
    !value.every((entry) => typeof entry === 'string' && entry.length > 0)
  ) {
    throw new ApiError(400, 'VALIDATION', `${field} 必须是字符串数组`)
  }
}

/** 按 kind 校验 state 的最小形状（不校验跨实体引用） */
export function validateStateShape(kind: EntityKind, state: unknown): void {
  if (!isRecord(state)) throw new ApiError(400, 'VALIDATION', 'state 必须是 JSON 对象')

  switch (kind) {
    case 'progress-node': {
      if ('successors' in state || 'is_entry' in state) {
        throw new ApiError(400, 'VALIDATION', 'progress-node 不允许携带拓扑字段')
      }
      if (typeof state.stable_id !== 'string' || !state.stable_id) {
        throw new ApiError(400, 'VALIDATION', 'progress-node.stable_id 必填')
      }
      if (!['normal', 'branch', 'merge'].includes(state.node_kind as string)) {
        throw new ApiError(400, 'VALIDATION', 'progress-node.node_kind 非法')
      }
      if (typeof state.triggers_checkpoint !== 'boolean') {
        throw new ApiError(400, 'VALIDATION', 'progress-node.triggers_checkpoint 必须为布尔')
      }
      return
    }
    case 'file-tree-node': {
      if ('parent_stable_id' in state || 'parent' in state) {
        throw new ApiError(400, 'VALIDATION', 'file-tree-node 不允许携带 parent 挂接字段')
      }
      if (typeof state.stable_id !== 'string' || !state.stable_id) {
        throw new ApiError(400, 'VALIDATION', 'file-tree-node.stable_id 必填')
      }
      if (!['directory', 'file'].includes(state.kind as string)) {
        throw new ApiError(400, 'VALIDATION', 'file-tree-node.kind 必须为 directory 或 file')
      }
      if (typeof state.name !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'file-tree-node.name 必填')
      }
      if (!isRecord(state.display)) {
        throw new ApiError(400, 'VALIDATION', 'file-tree-node.display 必须是对象')
      }
      if (typeof state.hidden !== 'boolean') {
        throw new ApiError(400, 'VALIDATION', 'file-tree-node.hidden 必须为布尔')
      }
      return
    }
    case 'file-tree': {
      if (state.root_stable_id !== null && typeof state.root_stable_id !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'file-tree.root_stable_id 必须为字符串或 null')
      }
      if (!isRecord(state.children)) {
        throw new ApiError(400, 'VALIDATION', 'file-tree.children 必须是 parent → children[] 映射')
      }
      for (const [parent, children] of Object.entries(state.children)) {
        if (!parent) throw new ApiError(400, 'VALIDATION', 'file-tree.children 的键不能为空')
        assertStringArray(children, `file-tree.children[${parent}]`)
      }
      return
    }
    case 'progress-dag': {
      assertStringArray(state.entry_stable_ids, 'progress-dag.entry_stable_ids')
      if (!isRecord(state.successors)) {
        throw new ApiError(400, 'VALIDATION', 'progress-dag.successors 必须是 from → to[] 映射')
      }
      for (const [from, targets] of Object.entries(state.successors)) {
        if (!from) throw new ApiError(400, 'VALIDATION', 'progress-dag.successors 的键不能为空')
        assertStringArray(targets, `progress-dag.successors[${from}]`)
      }
      return
    }
    case 'asset': {
      if (typeof state.file_id !== 'string' || !state.file_id) {
        throw new ApiError(400, 'VALIDATION', 'asset.file_id 必填')
      }
      if (typeof state.media_type !== 'string' || !state.media_type) {
        throw new ApiError(400, 'VALIDATION', 'asset.media_type 必填')
      }
      return
    }
    case 'hint': {
      if (typeof state.stable_id !== 'string' || !state.stable_id) {
        throw new ApiError(400, 'VALIDATION', 'hint.stable_id 必填')
      }
      if (typeof state.source_asset_id !== 'string' || !state.source_asset_id) {
        throw new ApiError(400, 'VALIDATION', 'hint.source_asset_id 必填')
      }
      if (typeof state.download_name !== 'string' || !state.download_name) {
        throw new ApiError(400, 'VALIDATION', 'hint.download_name 必填')
      }
      if (typeof state.credit_id !== 'string' || !state.credit_id) {
        throw new ApiError(400, 'VALIDATION', 'hint.credit_id 必填')
      }
      if (
        typeof state.credit_amount !== 'number' ||
        !Number.isInteger(state.credit_amount) ||
        state.credit_amount <= 0
      ) {
        throw new ApiError(400, 'VALIDATION', 'hint.credit_amount 必须为正整数')
      }
      if (!isRecord(state.display) || typeof state.display.title !== 'string' || !state.display.title) {
        throw new ApiError(400, 'VALIDATION', 'hint.display.title 必填')
      }
      return
    }
    case 'script': {
      if (typeof state.stable_id !== 'string' || !state.stable_id) {
        throw new ApiError(400, 'VALIDATION', 'script.stable_id 必填')
      }
      if (typeof state.revision !== 'number') {
        throw new ApiError(400, 'VALIDATION', 'script.revision 必须为数字')
      }
      if (!isRecord(state.body) || !Array.isArray(state.body.lines)) {
        throw new ApiError(400, 'VALIDATION', 'script.body 必须含 lines 数组')
      }
      return
    }
    case 'validation': {
      if (typeof state.stable_id !== 'string' || !state.stable_id) {
        throw new ApiError(400, 'VALIDATION', 'validation.stable_id 必填')
      }
      if (typeof state.validation_id !== 'string' || !state.validation_id) {
        throw new ApiError(400, 'VALIDATION', 'validation.validation_id 必填')
      }
      return
    }
    case 'artifact-template': {
      if (typeof state.artifact_id !== 'string' || !state.artifact_id) {
        throw new ApiError(400, 'VALIDATION', 'artifact-template.artifact_id 必填')
      }
      if (typeof state.media_type !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'artifact-template.media_type 必填')
      }
      return
    }
    case 'artifact-node': {
      if (typeof state.stable_id !== 'string' || !state.stable_id) {
        throw new ApiError(400, 'VALIDATION', 'artifact-node.stable_id 必填')
      }
      if (typeof state.path !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'artifact-node.path 必填')
      }
      if (typeof state.artifact_locator !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'artifact-node.artifact_locator 必填')
      }
      if (!isRecord(state.display)) {
        throw new ApiError(400, 'VALIDATION', 'artifact-node.display 必须是对象')
      }
      if (typeof state.hidden !== 'boolean') {
        throw new ApiError(400, 'VALIDATION', 'artifact-node.hidden 必须为布尔')
      }
      return
    }
    case 'account-template': {
      if (typeof state.account_id !== 'string' || !state.account_id) {
        throw new ApiError(400, 'VALIDATION', 'account-template.account_id 必填')
      }
      if (typeof state.display_name !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'account-template.display_name 必填')
      }
      if (typeof state.permission !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'account-template.permission 必填')
      }
      if (!isRecord(state.metadata)) {
        throw new ApiError(400, 'VALIDATION', 'account-template.metadata 必须是对象')
      }
      return
    }
    case 'credit-template': {
      if (typeof state.credit_id !== 'string' || !state.credit_id) {
        throw new ApiError(400, 'VALIDATION', 'credit-template.credit_id 必填')
      }
      if (typeof state.display_name !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'credit-template.display_name 必填')
      }
      if (!isRecord(state.metadata)) {
        throw new ApiError(400, 'VALIDATION', 'credit-template.metadata 必须是对象')
      }
      return
    }
    case 'achievement': {
      if (typeof state.achievement_id !== 'string' || !state.achievement_id) {
        throw new ApiError(400, 'VALIDATION', 'achievement.achievement_id 必填')
      }
      if (typeof state.secret !== 'boolean') {
        throw new ApiError(400, 'VALIDATION', 'achievement.secret 必须为布尔')
      }
      if (!isRecord(state.display)) {
        throw new ApiError(400, 'VALIDATION', 'achievement.display 必须是对象')
      }
      return
    }
    case 'task': {
      if (typeof state.task_id !== 'string' || !state.task_id) {
        throw new ApiError(400, 'VALIDATION', 'task.task_id 必填')
      }
      assertStringArray(state.dependencies, 'task.dependencies')
      return
    }
    case 'event-listener': {
      if (typeof state.event_type !== 'string' || !state.event_type) {
        throw new ApiError(400, 'VALIDATION', 'event-listener.event_type 必填')
      }
      if (typeof state.priority !== 'number') {
        throw new ApiError(400, 'VALIDATION', 'event-listener.priority 必须为数字')
      }
      assertStringArray(state.dependencies, 'event-listener.dependencies')
      return
    }
    case 'python-block': {
      if (typeof state.name !== 'string' || !state.name) {
        throw new ApiError(400, 'VALIDATION', 'python-block.name 必填')
      }
      if (!(PYTHON_SLOTS as readonly string[]).includes(state.slot as string)) {
        throw new ApiError(400, 'VALIDATION', 'python-block.slot 非法')
      }
      if (typeof state.content !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'python-block.content 必须为字符串')
      }
      return
    }
  }
}

export function createEntity(
  projectId: string,
  input: CreateEntityInput,
  authorId: string,
  db: Database.Database = getDatabase(),
): Entity {
  const kind = assertKind(input.kind)
  const uiKind = assertUiKind(kind, input.ui_kind)
  const group = assertGroup(input.group)
  const resourceId = assertResourceId(kind, input.resource_id)
  validateStateShape(kind, input.state)

  const now = new Date().toISOString()
  const id = randomUUID()
  try {
    db.prepare(
      `INSERT INTO entities (id, project_id, "group", kind, ui_kind, resource_id, revision, version, state, created_at, updated_at)
       VALUES (@id, @project_id, @group, @kind, @ui_kind, @resource_id, 1, 1, @state, @now, @now)`,
    ).run({
      id,
      project_id: projectId,
      group,
      kind,
      ui_kind: uiKind,
      resource_id: resourceId,
      state: JSON.stringify(input.state),
      now,
    })
  } catch (error) {
    if (isSqliteConstraintError(error)) {
      throw new ApiError(409, 'RESOURCE_CONFLICT', 'resource_id 在项目内已存在')
    }
    throw error
  }
  const row = findRow(db, projectId, id)
  if (!row) throw new Error('entity insert did not persist')
  return toEntity(row)
}

export function findEntity(
  projectId: string,
  entityId: string,
  db: Database.Database = getDatabase(),
): Entity | undefined {
  const row = findRow(db, projectId, entityId)
  return row ? toEntity(row) : undefined
}

export function requireEntity(
  projectId: string,
  entityId: string,
  db: Database.Database = getDatabase(),
): Entity {
  const entity = findEntity(projectId, entityId, db)
  if (!entity) throw new ApiError(404, 'ENTITY_NOT_FOUND', '实体不存在')
  return entity
}

export function listProjectEntities(
  projectId: string,
  db: Database.Database = getDatabase(),
): Entity[] {
  const rows = db
    .prepare('SELECT * FROM entities WHERE project_id = ? ORDER BY id ASC')
    .all(projectId) as EntityRow[]
  return rows.map(toEntity)
}

interface AppliedPatch {
  state: string
  group: string
  resource_id: string
  op: PatchOp
  value: unknown
}

function assertPatchOp(value: unknown): PatchOp {
  if (value === undefined || value === 'set') return 'set'
  if (value === 'remove') return 'remove'
  throw new ApiError(400, 'VALIDATION', "op 必须是 'set' 或 'remove'")
}

/** 解析并应用 data_path；返回更新后的列值（不做历史与版本递增） */
export function applyDataPath(
  row: EntityRow,
  dataPath: string,
  value: unknown,
  op: PatchOp = 'set',
): AppliedPatch {
  const parsed = parseDataPath(dataPath, row.id)
  if (!parsed) throw new ApiError(400, 'VALIDATION', 'data_path 非法')
  const resolvedOp = assertPatchOp(op)
  if (resolvedOp === 'set' && value === undefined) {
    throw new ApiError(400, 'VALIDATION', 'set 操作必须提供 value')
  }

  if (parsed.root === 'state') {
    const state = JSON.parse(row.state) as Record<string, unknown>
    const nextState =
      resolvedOp === 'remove'
        ? removeJsonPointer(state, parsed.json_path)
        : setJsonPointer(state, parsed.json_path, value)
    return {
      state: JSON.stringify(nextState),
      group: row.group,
      resource_id: row.resource_id,
      op: resolvedOp,
      value: resolvedOp === 'remove' ? undefined : value,
    }
  }
  if (resolvedOp === 'remove') {
    throw new ApiError(400, 'VALIDATION', 'group/resource_id 不支持 remove 操作')
  }
  if (parsed.root === 'group') {
    if (typeof value !== 'string' || !isValidGroup(value)) {
      throw new ApiError(400, 'VALIDATION', 'group 必须是 Python 模块路径段格式')
    }
    return { state: row.state, group: value, resource_id: row.resource_id, op: resolvedOp, value }
  }
  // resource_id
  if (typeof value !== 'string' || !isValidResourceIdForKind(row.kind, value)) {
    throw new ApiError(400, 'VALIDATION', 'resource_id 格式非法或命名空间与 kind 不匹配')
  }
  return { state: row.state, group: row.group, resource_id: value, op: resolvedOp, value }
}

export function patchEntity(
  projectId: string,
  entityId: string,
  dataPath: string,
  value: unknown,
  authorId: string,
  op: PatchOp = 'set',
  db: Database.Database = getDatabase(),
): Entity {
  const apply = db.transaction(() => {
    const row = findRow(db, projectId, entityId)
    if (!row) throw new ApiError(404, 'ENTITY_NOT_FOUND', '实体不存在')
    const applied = applyDataPath(row, dataPath, value, op)

    if (applied.resource_id !== row.resource_id) {
      const conflict = db
        .prepare('SELECT id FROM entities WHERE project_id = ? AND resource_id = ? AND id <> ?')
        .get(projectId, applied.resource_id, entityId)
      if (conflict) {
        throw new ApiError(409, 'RESOURCE_CONFLICT', 'resource_id 在项目内已存在')
      }
    }

    const now = new Date().toISOString()
    db.prepare(
      `INSERT INTO entity_history (entity_id, version, state, author_id, created_at)
       VALUES (?, ?, ?, ?, ?)`,
    ).run(entityId, row.version, row.state, authorId, now)

    const limit = getEntityHistoryLimit(db)
    const pruneBefore = row.version - limit
    if (pruneBefore > 0) {
      db.prepare('DELETE FROM entity_history WHERE entity_id = ? AND version <= ?').run(
        entityId,
        pruneBefore,
      )
    }

    db.prepare(
      `UPDATE entities
       SET "group" = @group, resource_id = @resource_id, state = @state,
           revision = @revision, version = @version, updated_at = @updated_at
       WHERE id = @id`,
    ).run({
      id: entityId,
      group: applied.group,
      resource_id: applied.resource_id,
      state: applied.state,
      revision: row.revision + 1,
      version: row.version + 1,
      updated_at: now,
    })

    const updated = findRow(db, projectId, entityId)
    if (!updated) throw new Error('entity patch did not persist')
    return updated
  })

  return toEntity(apply())
}

export function rollbackEntity(
  projectId: string,
  entityId: string,
  authorId: string,
  db: Database.Database = getDatabase(),
): Entity {
  const apply = db.transaction(() => {
    const row = findRow(db, projectId, entityId)
    if (!row) throw new ApiError(404, 'ENTITY_NOT_FOUND', '实体不存在')
    const previousVersion = row.version - 1
    const snapshot = db
      .prepare(
        'SELECT state FROM entity_history WHERE entity_id = ? AND version = ?',
      )
      .get(entityId, previousVersion) as { state: string } | undefined
    if (!snapshot) {
      throw new ApiError(409, 'HISTORY_EMPTY', '没有可回退的历史快照')
    }

    db.prepare('DELETE FROM entity_history WHERE entity_id = ? AND version = ?').run(
      entityId,
      previousVersion,
    )

    const now = new Date().toISOString()
    db.prepare(
      `UPDATE entities
       SET state = @state, revision = @revision, version = @version, updated_at = @updated_at
       WHERE id = @id`,
    ).run({
      id: entityId,
      state: snapshot.state,
      revision: row.revision + 1,
      version: previousVersion,
      updated_at: now,
    })

    const updated = findRow(db, projectId, entityId)
    if (!updated) throw new Error('entity rollback did not persist')
    return updated
  })

  return toEntity(apply())
}

export function deleteEntity(
  projectId: string,
  entityId: string,
  db: Database.Database = getDatabase(),
): boolean {
  const result = db
    .prepare('DELETE FROM entities WHERE id = ? AND project_id = ?')
    .run(entityId, projectId)
  return result.changes > 0
}

export function listHistory(
  projectId: string,
  entityId: string,
  db: Database.Database = getDatabase(),
): EntityHistoryEntry[] {
  requireEntity(projectId, entityId, db)
  const rows = db
    .prepare(
      'SELECT version, state, author_id, created_at FROM entity_history WHERE entity_id = ? ORDER BY version DESC',
    )
    .all(entityId) as Array<{
    version: number
    state: string
    author_id: string
    created_at: string
  }>
  return rows.map((row) => ({
    version: row.version,
    state: JSON.parse(row.state) as EntityState,
    author_id: row.author_id,
    created_at: row.created_at,
  }))
}

function findRow(
  db: Database.Database,
  projectId: string,
  entityId: string,
): EntityRow | undefined {
  return db
    .prepare('SELECT * FROM entities WHERE id = ? AND project_id = ?')
    .get(entityId, projectId) as EntityRow | undefined
}

/** 按 JSON Pointer 在对象/数组中写入值；set 允许创建缺失的容器/叶子字段（'' 表示整个 state） */
function setJsonPointer(
  root: Record<string, unknown>,
  pointer: string,
  value: unknown,
): Record<string, unknown> {
  if (pointer === '') {
    if (!isRecord(value)) throw new ApiError(400, 'VALIDATION', '整个 state 的替换值必须是对象')
    return value as Record<string, unknown>
  }
  const segments = pointerSegments(pointer)
  let current: unknown = root
  for (let index = 0; index < segments.length - 1; index += 1) {
    const segment = segments[index]
    if (segment === undefined) {
      throw new ApiError(400, 'VALIDATION', `data_path 路径段为空: ${pointer}`)
    }
    current = childForWrite(current, segment, pointer)
  }
  const last = segments[segments.length - 1]
  if (last === undefined) {
    throw new ApiError(400, 'VALIDATION', `data_path 路径段为空: ${pointer}`)
  }
  if (Array.isArray(current)) {
    const position = Number(last)
    if (!Number.isInteger(position) || position < 0 || position >= current.length) {
      throw new ApiError(400, 'VALIDATION', `data_path 数组下标越界: ${pointer}`)
    }
    current[position] = value
  } else if (isRecord(current)) {
    current[last] = value
  } else {
    throw new ApiError(400, 'VALIDATION', `data_path 无法写入: ${pointer}`)
  }
  return root
}

/** 定位写入路径的下一层；对象字段缺失时自动创建空对象，数组元素必须已存在 */
function childForWrite(current: unknown, segment: string, pointer: string): unknown {
  if (Array.isArray(current)) {
    const position = Number(segment)
    if (!Number.isInteger(position) || position < 0 || position >= current.length) {
      throw new ApiError(400, 'VALIDATION', `data_path 数组下标越界: ${pointer}`)
    }
    const child = current[position]
    if (!isRecord(child)) {
      throw new ApiError(400, 'VALIDATION', `data_path 无法写入: ${pointer}`)
    }
    return child
  }
  if (isRecord(current)) {
    if (!(segment in current)) {
      current[segment] = {}
    }
    const child = current[segment]
    if (!isRecord(child)) {
      throw new ApiError(400, 'VALIDATION', `data_path 无法写入: ${pointer}`)
    }
    return child
  }
  throw new ApiError(400, 'VALIDATION', `data_path 无法定位: ${pointer}`)
}

/** 按 JSON Pointer 删除对象键或数组元素；路径不存在时视为 no-op */
function removeJsonPointer(
  root: Record<string, unknown>,
  pointer: string,
): Record<string, unknown> {
  if (pointer === '') {
    throw new ApiError(400, 'VALIDATION', '不能移除整个 state')
  }
  const segments = pointerSegments(pointer)
  let current: unknown = root
  for (let index = 0; index < segments.length - 1; index += 1) {
    const segment = segments[index]
    if (segment === undefined) {
      throw new ApiError(400, 'VALIDATION', `data_path 路径段为空: ${pointer}`)
    }
    if (Array.isArray(current)) {
      const position = Number(segment)
      if (!Number.isInteger(position) || position < 0 || position >= current.length) return root
      current = current[position]
      continue
    }
    if (!isRecord(current) || !(segment in current)) return root
    current = current[segment]
  }
  const last = segments[segments.length - 1]
  if (last === undefined) {
    throw new ApiError(400, 'VALIDATION', `data_path 路径段为空: ${pointer}`)
  }
  if (Array.isArray(current)) {
    const position = Number(last)
    if (!Number.isInteger(position) || position < 0 || position >= current.length) return root
    current.splice(position, 1)
  } else if (isRecord(current) && last in current) {
    delete current[last]
  }
  return root
}

function pointerSegments(pointer: string): string[] {
  return pointer
    .slice(1)
    .split('/')
    .map((segment) => segment.replace(/~1/g, '/').replace(/~0/g, '~'))
}
