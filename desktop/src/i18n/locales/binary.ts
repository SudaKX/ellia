/**
 * # binary — 二进制语言包
 *
 * 将 en-US 所有文本递归转换为 8 位二进制（每组以空格分隔）。
 * FakeOS 风格彩蛋：终端/黑客氛围。
 *
 * @example
 * "Hello" → "01001000 01100101 01101100 01101100 01101111"
 */

import { enUS } from './en-US'
import type { LocaleMessages } from './en-US'

/** 将字符串转换为 8 位二进制（空格分隔） */
function toBinary(text: string): string {
  return Array.from(text, (c) => c.codePointAt(0)!.toString(2).padStart(8, '0')).join(' ')
}

/** 递归遍历对象，将所有字符串值转换为二进制 */
function deepBinary(obj: unknown): unknown {
  if (typeof obj === 'string') return toBinary(obj)
  if (Array.isArray(obj)) return obj.map(deepBinary)
  if (obj && typeof obj === 'object') {
    const result: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      result[key] = deepBinary(value)
    }
    return result
  }
  return obj
}

export const binary = deepBinary(enUS) as LocaleMessages
