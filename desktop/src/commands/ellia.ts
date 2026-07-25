/**
 * # ellia — ElLInA 终端彩蛋
 *
 * 在终端中呼叫 ElLInA，显示 ASCII 艺术 + 随机台词。
 * 支持颜色参数：`ellia blue|yellow|green|red`，默认浅蓝色。
 *
 * @example
 * ```
 * > ellia
 *    /\
 *   /  \
 *  /_/\_\
 * [ElLInA] 你好，PLAYER。
 * ```
 * ```
 * > ellia red
 *    /\
 *   /  \
 *  /_/\_\
 * [ElLInA] 有些文件……不是你现在该看的。  (红色)
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'

/** HTML 行标记前缀（与 Terminal.vue 中的 HTML_MARKER 一致） */
const HTML_MARKER = '\x00'

/** 可选颜色映射 */
const COLOR_MAP: Record<string, string> = {
  blue: '#5b9bd5',
  yellow: '#d4a853',
  green: 'var(--signal-mint)',
  red: 'var(--signal-red)',
}

/** 默认颜色（浅蓝） */
const DEFAULT_COLOR = COLOR_MAP.blue

/** ElLInA ASCII 艺术 */
const ELLIA_ASCII = [
  '   /\\',
  '  /  \\',
  ' /_/\\_\\',
]

/** 台词 i18n key */
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
  execute(args: string[], ctx: CommandContext) {
    const colorName = args[0]?.toLowerCase()
    const color = COLOR_MAP[colorName] ?? DEFAULT_COLOR

    const asciiLines = ELLIA_ASCII.map(
      (line) => `<span style="color:${color}">${line}</span>`,
    )

    // 随机选 1-2 句台词
    const count = 1 + Math.floor(Math.random() * 2)
    const shuffled = [...ELLIA_LINE_KEYS].sort(() => Math.random() - 0.5)

    const quoteLines: string[] = []
    for (let i = 0; i < count; i++) {
      if (shuffled[i]) {
        const text = ctx.t(shuffled[i], { user: ctx.user })
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
        quoteLines.push(`<span style="color:${color}">${text}</span>`)
      }
    }

    // 合并为单行 HTML，用 <br> 分隔
    return [HTML_MARKER + [...asciiLines, ...quoteLines].join('<br>')]
  },
})
