/**
 * # ellia — ElLInA 终端彩蛋
 *
 * 在终端中呼叫 ElLInA，显示 ASCII 艺术 + 随机台词。
 * 台词列表包含叙事暗示。
 *
 * ## ASCII 艺术
 *
 * 使用简单的字符画，避免过宽（终端窗口约 50-55 列）。
 *
 * ## i18n 设计
 *
 * 台词内容存储在 i18n locale 文件中（`terminal.ellia.line0` ~ `line5`），
 * 通过 `ctx.t()` 在运行时解析。这样切换语言时台词自动跟随。
 *
 * @example
 * ```
 * > ellia
 *    /\
 *   /  \
 *  /_/\_\
 * [ElLInA] 你好，PLAYER。
 * [ElLInA] 有些文件……不是你现在该看的。
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'

/** ElLInA ASCII 艺术（语言无关，纯字符画） */
const ELLIA_ASCII = [
  '   /\\',
  '  /  \\',
  ' /_/\\_\\',
]

/**
 * ElLInA 台词 i18n key 数组。
 * 不在模块顶层用 `ctx.t()` 预解析——因为模块加载时 locale 可能尚未初始化，
 * 因此在 execute() 中动态调用 `ctx.t()` 获取当前语言的翻译。
 */
const ELLIA_LINE_KEYS = [
  'terminal.ellia.line0',
  'terminal.ellia.line1',
  'terminal.ellia.line2',
  'terminal.ellia.line3',
  'terminal.ellia.line4',
  'terminal.ellia.line5',
]

registerCommand({
  name: 'ellia',
  descriptionKey: 'terminal.commands.ellia.description',
  execute(_args: string[], ctx: CommandContext) {
    const lines = [...ELLIA_ASCII]

    // 随机选 1-2 句台词，每次调用结果不同
    const count = 1 + Math.floor(Math.random() * 2)
    const shuffled = [...ELLIA_LINE_KEYS].sort(() => Math.random() - 0.5)

    for (let i = 0; i < count; i++) {
      if (shuffled[i]) {
        // 通过 ctx.t() 解析 i18n key，{user} 占位符替换为当前用户名
        lines.push(ctx.t(shuffled[i], { user: ctx.user }))
      }
    }

    return lines
  },
})
