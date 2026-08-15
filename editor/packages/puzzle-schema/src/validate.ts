// @ellia/puzzle-schema — 编辑期轻量校验（plan-v1.md §10、handoff.md §3）
// 仅表单即时提示；导出前不做校验（正确性由 mythos 侧验证）。

import { isPythonName } from './python.js'

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

/** stable_id 全项目唯一、非空、无空白字符（唯一性由后端按项目校验） */
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

export { isPythonName }
