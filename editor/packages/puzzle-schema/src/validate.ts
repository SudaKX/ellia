// @ellia/puzzle-schema — 编辑期/服务端轻量校验（plan-v2 §3.4/§5.1）
// 仅字段与格式校验；跨实体引用与悬空引用不做检查。

import { isPythonName } from './python.js'
import {
  RESOURCE_NAMESPACES,
  UI_KINDS,
  namespaceFor,
  uiKindFor,
  type EntityKind,
  type ResourceNamespace,
  type UiKind,
} from './types.js'

/** module_id 必须是单一路径段（不能是 . / ..，不含路径分隔符） */
export function isValidModuleId(value: string): boolean {
  if (!value || value === '.' || value === '..') return false
  return !value.includes('/') && !value.includes('\\')
}

/** validation_id 为 slug 格式 */
export const VALIDATION_ID_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

export function isValidValidationId(value: string): boolean {
  return VALIDATION_ID_RE.test(value)
}

/** stable_id 项目内唯一、非空、无空白字符 */
export function isValidStableId(value: string): boolean {
  return value.trim().length > 0 && !/\s/.test(value)
}

/** Hint 引用的 credit_id 必须已注册（编辑器表单即时提示） */
export function isHintCreditRegistered(
  creditId: string,
  registeredCreditIds: readonly string[],
): boolean {
  return registeredCreditIds.includes(creditId)
}

/**
 * 规范相对路径（对齐 mythos is_canonical_source_relative_path）：
 * 非空、不以 / 开头、不含 \ 与 :、每个路径段非空且不是 . / ..
 */
export function isCanonicalRelativePath(value: string): boolean {
  return (
    value.length > 0 &&
    !value.startsWith('/') &&
    !value.includes('\\') &&
    !value.includes(':') &&
    value.split('/').every((part) => part.length > 0 && part !== '.' && part !== '..')
  )
}

/** entity group：Python 模块路径段，默认 main */
export const GROUP_RE = /^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$/

export function isValidGroup(value: string): boolean {
  return GROUP_RE.test(value)
}

export interface ParsedResourceId {
  namespace: ResourceNamespace
  id: string
}

/**
 * 解析 resource_id（<namespace>:<id>，按第一个 `:` 分隔）。
 * id 部分不允许再含 `:`、不允许空白；asset-path 额外校验规范相对路径；
 * python-name 额外校验 Python 函数名。返回 null 表示非法。
 */
export function parseResourceId(value: string): ParsedResourceId | null {
  if (typeof value !== 'string' || value.length > 128) return null
  const colon = value.indexOf(':')
  if (colon <= 0 || colon === value.length - 1) return null
  const namespace = value.slice(0, colon)
  const id = value.slice(colon + 1)
  if (!(RESOURCE_NAMESPACES as readonly string[]).includes(namespace)) return null
  if (id.includes(':') || /\s/.test(id)) return null
  if (namespace === 'asset-path' && !isCanonicalRelativePath(id)) return null
  if (namespace === 'python-name' && !isPythonName(id)) return null
  return { namespace, id } as ParsedResourceId
}

/** 校验 resource_id 的前缀与 kind 的命名空间一致，且格式合法 */
export function isValidResourceIdForKind(kind: EntityKind, resourceId: string): boolean {
  const parsed = parseResourceId(resourceId)
  return parsed !== null && parsed.namespace === namespaceFor(kind)
}

export interface ParsedDataPath {
  entity_id: string
  root: 'state' | 'group' | 'resource_id'
  json_path: string
}

/** JSON Pointer 宽松校验：空串（整个 state）或以 / 开头、无空白 */
function isValidJsonPointer(value: string): boolean {
  if (value === '') return true
  return value.startsWith('/') && !/\s/.test(value)
}

/**
 * 解析 data_path：`<entity_id>@<root>:<json_path>`。
 * group/resource_id 的 json_path 必须为空；state 的 json_path 必须为合法 JSON Pointer。
 * 若传入 expectedEntityId，则 entity_id 部分必须一致。
 */
export function parseDataPath(
  dataPath: string,
  expectedEntityId?: string,
): ParsedDataPath | null {
  if (typeof dataPath !== 'string' || dataPath.length > 1024) return null
  const at = dataPath.indexOf('@')
  if (at <= 0) return null
  const entityId = dataPath.slice(0, at)
  const rest = dataPath.slice(at + 1)
  const colon = rest.indexOf(':')
  if (colon < 0) return null
  const root = rest.slice(0, colon)
  const jsonPath = rest.slice(colon + 1)
  if (root !== 'state' && root !== 'group' && root !== 'resource_id') return null
  if (root === 'group' || root === 'resource_id') {
    if (jsonPath !== '') return null
  } else if (!isValidJsonPointer(jsonPath)) {
    return null
  }
  if (expectedEntityId !== undefined && entityId !== expectedEntityId) return null
  if (entityId.trim().length === 0 || /\s/.test(entityId)) return null
  return { entity_id: entityId, root, json_path: jsonPath }
}

/** kind 允许的 ui_kind 列表（第一版一对一） */
export function allowedUiKinds(kind: EntityKind): UiKind[] {
  return [uiKindFor(kind)]
}

/** ui_kind 是否属于目录 */
export function isUiKind(value: string): value is UiKind {
  return (UI_KINDS as readonly string[]).includes(value)
}

export { isPythonName }
