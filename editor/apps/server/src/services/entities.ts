import { randomUUID } from 'node:crypto'

import {
  ENTITY_KINDS,
  EVENT_LISTENER_PRIORITIES,
  EVENT_LISTENER_TYPES,
  allowedUiKinds,
  isSafeDownloadName,
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
  comment: string
  created_at: string
  updated_at: string
}

export interface CreateEntityInput {
  group?: string
  kind: unknown
  ui_kind: unknown
  resource_id: string
  state: unknown
  comment?: string
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
    comment: row.comment,
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
    comment: entity.comment,
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
    throw new ApiError(400, 'VALIDATION', 'group 必须是单段 Python 模块名（不能包含点或路径分隔符）')
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
  const s = state as Record<string, unknown>

  function requiredString(field: string, label: string): void {
    if (s[field] === undefined || s[field] === null) {
      throw new ApiError(400, 'VALIDATION', `${label} 必填`)
    }
    if (typeof s[field] !== 'string') {
      throw new ApiError(400, 'VALIDATION', `${label} 必须是字符串`)
    }
  }

  switch (kind) {
    case 'progress-node': {
      if ('successors' in s || 'is_entry' in s || 'node_kind' in s || 'stable_id' in s) {
        throw new ApiError(400, 'VALIDATION', 'progress-node 不允许携带拓扑或旧节点字段')
      }
      if (typeof s.triggers_checkpoint !== 'boolean') {
        throw new ApiError(400, 'VALIDATION', 'progress-node.triggers_checkpoint 必须为布尔')
      }
      if (s.how !== undefined && s.how !== null && typeof s.how !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'progress-node.how 必须是字符串')
      }
      if (
        s.mode !== undefined &&
        s.mode !== null &&
        s.mode !== '' &&
        !['and', 'or'].includes(s.mode as string)
      ) {
        throw new ApiError(400, 'VALIDATION', 'progress-node.mode 必须为 and 或 or')
      }
      return
    }
    case 'file-node': {
      if (
        'parent_stable_id' in s ||
        'parent' in s ||
        'kind' in s ||
        'path' in s ||
        'children' in s ||
        'name' in s
      ) {
        throw new ApiError(400, 'VALIDATION', 'file-node 不允许携带 parent/kind/path/children/name 字段')
      }
      if (!isRecord(s.display)) {
        throw new ApiError(400, 'VALIDATION', 'file-node.display 必须是对象')
      }
      if (typeof s.hidden !== 'boolean') {
        throw new ApiError(400, 'VALIDATION', 'file-node.hidden 必须为布尔')
      }
      if (s.download_name !== undefined && s.download_name !== null) {
        if (typeof s.download_name !== 'string' || !isSafeDownloadName(s.download_name)) {
          throw new ApiError(400, 'VALIDATION', 'file-node.download_name 必须是安全下载文件名')
        }
      }
      if (s.source_asset !== undefined && s.source_asset !== null && typeof s.source_asset !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'file-node.source_asset 必须是字符串')
      }
      if (s.access_rule !== undefined && s.access_rule !== null && typeof s.access_rule !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'file-node.access_rule 必须是字符串')
      }
      return
    }
    case 'file-tree': {
      if (typeof s.rootId !== 'string' || s.rootId.length === 0) {
        throw new ApiError(400, 'VALIDATION', 'file-tree.rootId 必须为非空字符串')
      }
      if (!isRecord(s.nodes)) {
        throw new ApiError(400, 'VALIDATION', 'file-tree.nodes 必须是节点表')
      }
      if (!(s.rootId in s.nodes)) {
        throw new ApiError(400, 'VALIDATION', 'file-tree.rootId 必须存在于 nodes')
      }
      const namesByParent = new Map<string, Set<string>>()
      for (const [nodeId, rawNode] of Object.entries(s.nodes)) {
        if (!nodeId) throw new ApiError(400, 'VALIDATION', 'file-tree.nodes 的键不能为空')
        if (!isRecord(rawNode)) {
          throw new ApiError(400, 'VALIDATION', `file-tree.nodes[${nodeId}] 必须是对象`)
        }
        const node = rawNode as Record<string, unknown>
        if (node.id !== nodeId) {
          throw new ApiError(400, 'VALIDATION', `file-tree.nodes[${nodeId}].id 必须与键一致`)
        }
        if (typeof node.name !== 'string' || node.name.length === 0) {
          throw new ApiError(400, 'VALIDATION', `file-tree.nodes[${nodeId}].name 必须为非空字符串`)
        }
        if (nodeId !== s.rootId && node.parent === null) {
          throw new ApiError(400, 'VALIDATION', `file-tree.nodes[${nodeId}] 非根节点必须指定 parent`)
        }
        const parentKey = typeof node.parent === 'string' ? node.parent : ''
        const siblingNames = namesByParent.get(parentKey) ?? new Set<string>()
        if (siblingNames.has(node.name)) {
          throw new ApiError(400, 'VALIDATION', `file-tree 同级节点名称不能重复: ${node.name}`)
        }
        siblingNames.add(node.name)
        namesByParent.set(parentKey, siblingNames)
        if (typeof node.isDirectory !== 'boolean') {
          throw new ApiError(400, 'VALIDATION', `file-tree.nodes[${nodeId}].isDirectory 必须为布尔`)
        }
        if (node.isDirectory === true) {
          if (node.inode !== null) {
            throw new ApiError(400, 'VALIDATION', `file-tree.nodes[${nodeId}] 是文件夹，inode 必须为 null`)
          }
        } else {
          if (typeof node.inode !== 'string' || node.inode.length === 0) {
            throw new ApiError(400, 'VALIDATION', `file-tree.nodes[${nodeId}] 是文件，inode 必须为非空字符串`)
          }
        }
        if (node.parent !== null && typeof node.parent !== 'string') {
          throw new ApiError(400, 'VALIDATION', `file-tree.nodes[${nodeId}].parent 必须为字符串或 null`)
        }
        if (typeof node.order !== 'number' || !Number.isInteger(node.order) || node.order < 0) {
          throw new ApiError(400, 'VALIDATION', `file-tree.nodes[${nodeId}].order 必须为非负整数`)
        }
        if (nodeId === s.rootId) {
          if (node.name !== '/') {
            throw new ApiError(400, 'VALIDATION', 'file-tree 根节点 name 必须为 /')
          }
          if (node.isDirectory !== true) {
            throw new ApiError(400, 'VALIDATION', 'file-tree 根节点必须是文件夹')
          }
          if (node.inode !== null) {
            throw new ApiError(400, 'VALIDATION', 'file-tree 根节点 inode 必须为 null')
          }
          if (node.parent !== null) {
            throw new ApiError(400, 'VALIDATION', 'file-tree 根节点 parent 必须为 null')
          }
        } else if (node.parent !== null && !(node.parent in s.nodes)) {
          throw new ApiError(400, 'VALIDATION', `file-tree.nodes[${nodeId}].parent 引用了不存在的节点`)
        }
      }
      for (const node of Object.values(s.nodes) as Array<Record<string, unknown>>) {
        if (node.isDirectory === false && node.id !== undefined) {
          const hasChildren = Object.values(s.nodes).some(
            (child) => (child as Record<string, unknown>).parent === node.id,
          )
          if (hasChildren) {
            throw new ApiError(400, 'VALIDATION', `file-tree 文件节点不能包含子节点: ${String(node.id)}`)
          }
        }
      }
      return
    }
    case 'dag': {
      assertStringArray(s.entryIds, 'dag.entryIds')
      if (!isRecord(s.nodes)) {
        throw new ApiError(400, 'VALIDATION', 'dag.nodes 必须是 DagNodeId → DagNode 映射')
      }
      for (const [nodeId, rawNode] of Object.entries(s.nodes)) {
        if (!isRecord(rawNode)) {
          throw new ApiError(400, 'VALIDATION', `dag.nodes[${nodeId}] 必须是对象`)
        }
        const node = rawNode as Record<string, unknown>
        if (node.id !== nodeId) {
          throw new ApiError(400, 'VALIDATION', `dag.nodes[${nodeId}].id 必须与键一致`)
        }
        if (typeof node.id !== 'string' || node.id.length === 0) {
          throw new ApiError(400, 'VALIDATION', `dag.nodes[${nodeId}].id 必须为非空字符串`)
        }
        if (typeof node.name !== 'string' || node.name.trim().length === 0) {
          throw new ApiError(400, 'VALIDATION', `dag.nodes[${nodeId}].name 必须为非空字符串`)
        }
        if (node.pnode !== null && (typeof node.pnode !== 'string' || node.pnode.length === 0)) {
          throw new ApiError(400, 'VALIDATION', `dag.nodes[${nodeId}].pnode 必须为字符串或 null`)
        }
        assertStringArray(node.successors, `dag.nodes[${nodeId}].successors`)
        const successors = node.successors as string[]
        if (new Set(successors).size !== successors.length) {
          throw new ApiError(400, 'VALIDATION', `dag.nodes[${nodeId}].successors 不能包含重复后继`)
        }
        for (const successor of successors) {
          if (successor === nodeId) {
            throw new ApiError(400, 'VALIDATION', `dag.nodes[${nodeId}] 不能指向自身`)
          }
          if (!(successor in s.nodes)) {
            throw new ApiError(400, 'VALIDATION', `dag.nodes[${nodeId}].successors 引用了不存在的节点: ${successor}`)
          }
        }
      }
      for (const entryId of s.entryIds as string[]) {
        if (!(entryId in s.nodes)) {
          throw new ApiError(400, 'VALIDATION', `dag.entryIds 引用了不存在的节点: ${entryId}`)
        }
      }
      return
    }
    case 'asset': {
      requiredString('media_type', 'asset.media_type')
      if (s.file_reference !== undefined && s.file_reference !== null && typeof s.file_reference !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'asset.file_reference 必须是字符串')
      }
      if (s.source_reference !== undefined && s.source_reference !== null && typeof s.source_reference !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'asset.source_reference 必须是字符串')
      }
      return
    }
    case 'hint': {
      requiredString('source_asset_id', 'hint.source_asset_id')
      requiredString('download_name', 'hint.download_name')
      requiredString('credit_id', 'hint.credit_id')
      if (
        typeof s.credit_amount !== 'number' ||
        !Number.isInteger(s.credit_amount) ||
        s.credit_amount <= 0
      ) {
        throw new ApiError(400, 'VALIDATION', 'hint.credit_amount 必须为正整数')
      }
      if (!isRecord(s.display)) {
        throw new ApiError(400, 'VALIDATION', 'hint.display 必须是对象')
      }
      if (s.display.title === undefined || s.display.title === null) {
        throw new ApiError(400, 'VALIDATION', 'hint.display.title 必填')
      }
      if (typeof s.display.title !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'hint.display.title 必须是字符串')
      }
      return
    }
    case 'script': {
      if (typeof s.revision !== 'number') {
        throw new ApiError(400, 'VALIDATION', 'script.revision 必须为数字')
      }
      if (!isRecord(s.body) || !Array.isArray(s.body.lines)) {
        throw new ApiError(400, 'VALIDATION', 'script.body 必须含 lines 数组')
      }
      return
    }
    case 'validation': {
      requiredString('validation_id', 'validation.validation_id')
      return
    }
    case 'artifact': {
      requiredString('media_type', 'artifact.media_type')
      return
    }
    case 'artifact-node': {
      requiredString('artifact', 'artifact-node.artifact')
      requiredString('node_generator', 'artifact-node.node_generator')
      if (!isRecord(s.display)) {
        throw new ApiError(400, 'VALIDATION', 'artifact-node.display 必须是对象')
      }
      if (typeof s.display.label !== 'string' || s.display.label.trim() === '') {
        throw new ApiError(400, 'VALIDATION', 'artifact-node.display.label 必填且不能为空')
      }
      if (typeof s.hidden !== 'boolean') {
        throw new ApiError(400, 'VALIDATION', 'artifact-node.hidden 必须为布尔')
      }
      if (s.download_name !== undefined && s.download_name !== null) {
        if (typeof s.download_name !== 'string' || !isSafeDownloadName(s.download_name)) {
          throw new ApiError(400, 'VALIDATION', 'artifact-node.download_name 必须是安全下载文件名')
        }
      }
      return
    }
    case 'account': {
      requiredString('display_name', 'account.display_name')
      if (typeof s.permission !== 'number' || !Number.isInteger(s.permission)) {
        throw new ApiError(400, 'VALIDATION', 'account.permission 必须为整数')
      }
      if (!isRecord(s.metadata)) {
        throw new ApiError(400, 'VALIDATION', 'account.metadata 必须是对象')
      }
      return
    }
    case 'credit': {
      requiredString('display_name', 'credit.display_name')
      if (!isRecord(s.metadata)) {
        throw new ApiError(400, 'VALIDATION', 'credit.metadata 必须是对象')
      }
      return
    }
    case 'achievement': {
      if (typeof s.immediate !== 'boolean') {
        throw new ApiError(400, 'VALIDATION', 'achievement.immediate 必须为布尔')
      }
      if (!isRecord(s.meta)) {
        throw new ApiError(400, 'VALIDATION', 'achievement.meta 必须是对象')
      }
      if (s.condition !== undefined && s.condition !== null && typeof s.condition !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'achievement.condition 必须是字符串')
      }
      requiredString('effect', 'achievement.effect')
      return
    }
    case 'task': {
      requiredString('handler_block_id', 'task.handler_block_id')
      if (
        typeof s.dependencies !== 'number' ||
        !Number.isInteger(s.dependencies) ||
        s.dependencies < 0
      ) {
        throw new ApiError(400, 'VALIDATION', 'task.dependencies 必须为非负整数位掩码')
      }
      return
    }
    case 'listener': {
      requiredString('event_type', 'listener.event_type')
      if (!(EVENT_LISTENER_TYPES as readonly { value: string }[]).some((option) => option.value === s.event_type)) {
        throw new ApiError(400, 'VALIDATION', 'listener.event_type 非法')
      }
      requiredString('listener_block_id', 'listener.listener_block_id')
      if (!(EVENT_LISTENER_PRIORITIES as readonly { value: string }[]).some((option) => option.value === s.priority)) {
        throw new ApiError(400, 'VALIDATION', 'listener.priority 必须为 early/default/late')
      }
      if (
        typeof s.dependencies !== 'number' ||
        !Number.isInteger(s.dependencies) ||
        s.dependencies < 0
      ) {
        throw new ApiError(400, 'VALIDATION', 'listener.dependencies 必须为非负整数位掩码')
      }
      return
    }
    case 'code': {
      if (typeof s.content !== 'string') {
        throw new ApiError(400, 'VALIDATION', 'code.content 必须为字符串')
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
  const comment = input.comment ?? ''
  try {
    db.prepare(
      `INSERT INTO entities (id, project_id, "group", kind, ui_kind, resource_id, revision, version, state, comment, created_at, updated_at)
       VALUES (@id, @project_id, @group, @kind, @ui_kind, @resource_id, 1, 1, @state, @comment, @now, @now)`,
    ).run({
      id,
      project_id: projectId,
      group,
      kind,
      ui_kind: uiKind,
      resource_id: resourceId,
      state: JSON.stringify(input.state),
      comment,
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
  comment: string
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
      comment: row.comment,
      op: resolvedOp,
      value: resolvedOp === 'remove' ? undefined : value,
    }
  }
  if (resolvedOp === 'remove') {
    throw new ApiError(400, 'VALIDATION', 'group/resource_id/comment 不支持 remove 操作')
  }
  if (parsed.root === 'group') {
    if (typeof value !== 'string' || !isValidGroup(value)) {
      throw new ApiError(400, 'VALIDATION', 'group 必须是单段 Python 模块名（不能包含点或路径分隔符）')
    }
    return { state: row.state, group: value, resource_id: row.resource_id, comment: row.comment, op: resolvedOp, value }
  }
  if (parsed.root === 'comment') {
    if (typeof value !== 'string') {
      throw new ApiError(400, 'VALIDATION', 'comment 必须是字符串')
    }
    return { state: row.state, group: row.group, resource_id: row.resource_id, comment: value, op: resolvedOp, value }
  }
  // resource_id
  if (typeof value !== 'string' || !isValidResourceIdForKind(row.kind, value)) {
    throw new ApiError(400, 'VALIDATION', 'resource_id 格式非法或命名空间与 kind 不匹配')
  }
  return { state: row.state, group: row.group, resource_id: value, comment: row.comment, op: resolvedOp, value }
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
    const historySnapshot = JSON.stringify({
      group: row.group,
      resource_id: row.resource_id,
      comment: row.comment,
      state: JSON.parse(row.state) as EntityState,
    })
    db.prepare(
      `INSERT INTO entity_history (entity_id, version, state, author_id, created_at)
       VALUES (?, ?, ?, ?, ?)`,
    ).run(entityId, row.version, historySnapshot, authorId, now)

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
           comment = @comment, revision = @revision, version = @version, updated_at = @updated_at
       WHERE id = @id`,
    ).run({
      id: entityId,
      group: applied.group,
      resource_id: applied.resource_id,
      state: applied.state,
      comment: applied.comment,
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
    const parsed = JSON.parse(snapshot.state) as {
      group: string
      resource_id: string
      comment: string
      state: EntityState
    }

    if (parsed.resource_id !== row.resource_id) {
      const conflict = db
        .prepare('SELECT id FROM entities WHERE project_id = ? AND resource_id = ? AND id <> ?')
        .get(projectId, parsed.resource_id, entityId)
      if (conflict) {
        throw new ApiError(409, 'RESOURCE_CONFLICT', 'resource_id 在项目内已存在')
      }
    }

    db.prepare('DELETE FROM entity_history WHERE entity_id = ? AND version = ?').run(
      entityId,
      previousVersion,
    )

    const now = new Date().toISOString()
    db.prepare(
      `UPDATE entities
       SET "group" = @group, resource_id = @resource_id, state = @state,
           comment = @comment, revision = @revision, version = @version, updated_at = @updated_at
       WHERE id = @id`,
    ).run({
      id: entityId,
      group: parsed.group,
      resource_id: parsed.resource_id,
      state: JSON.stringify(parsed.state),
      comment: parsed.comment,
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
  return rows.map((row) => {
    const parsed = JSON.parse(row.state) as {
      group: string
      resource_id: string
      comment: string
      state: EntityState
    }
    return {
      version: row.version,
      group: parsed.group,
      resource_id: parsed.resource_id,
      comment: parsed.comment,
      state: parsed.state,
      author_id: row.author_id,
      created_at: row.created_at,
    }
  })
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
