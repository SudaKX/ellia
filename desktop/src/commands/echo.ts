/**
 * # echo — 回显文本
 *
 * 将参数拼接后输出。支持彩色文本标记和自动去除双引号。
 *
 * ## 彩色语法
 *
 * ```
 * echo {red}ERROR{/}: something went wrong
 * echo {green}SUCCESS{/} {blue}OK{/}
 * ```
 *
 * 可用颜色：{red} {green} {blue} {yellow} {cyan} {magenta} {white}
 * 结束标记：{/}
 *
 * ## 双引号
 *
 * 参数两端有双引号时自动去除：
 * ```
 * echo "hello world"
 * → hello world
 * ```
 *
 * @example
 * ```
 * > echo Hello World
 * Hello World
 * > echo "Hello World"
 * Hello World
 * > echo {red}Error{/}: file not found
 * Error: file not found  (红色 "Error")
 * ```
 */

import { registerCommand } from '@/registries/commands'

/** HTML 行标记前缀（与 Terminal.vue 中的 HTML_MARKER 一致） */
const HTML_MARKER = '\x00'

/** 颜色名 → CSS 值映射 */
const COLORS: Record<string, string> = {
  red: 'var(--signal-red)',
  green: 'var(--signal-mint)',
  blue: '#5b9bd5',
  yellow: '#d4a853',
  cyan: '#4ec9b0',
  magenta: '#c586c0',
  white: 'var(--text-primary)',
}

/** 颜色标记正则：匹配 {color} 或 {/} */
const COLOR_RE = /\{(red|green|blue|yellow|cyan|magenta|white)\}|\{\/\}/g

/**
 * 去除参数两端的双引号。
 * 如 `"hello"` → `hello`，`"hello world"` → `hello world`
 */
function stripQuotes(arg: string): string {
  if (arg.length >= 2 && arg.startsWith('"') && arg.endsWith('"')) {
    return arg.slice(1, -1)
  }
  return arg
}

/**
 * 将 {color}...{/} 标记转换为 HTML <span> 标签。
 */
function parseColorMarkers(text: string): string {
  const stack: string[] = []
  let result = ''
  let lastIndex = 0

  let match: RegExpExecArray | null
  while ((match = COLOR_RE.exec(text)) !== null) {
    // 追加标记前的普通文本
    result += escapeHtml(text.slice(lastIndex, match.index))

    if (match[0] === '{/}') {
      // 关闭当前颜色
      if (stack.length > 0) {
        stack.pop()
        result += '</span>'
      }
    } else {
      // 开启新颜色
      const colorName = match[1]
      const cssColor = COLORS[colorName]
      stack.push(colorName)
      result += `<span style="color:${cssColor}">`
    }

    lastIndex = COLOR_RE.lastIndex
  }

  // 追加剩余文本
  result += escapeHtml(text.slice(lastIndex))

  // 关闭未闭合的标签
  while (stack.length > 0) {
    stack.pop()
    result += '</span>'
  }

  return result
}

/** 转义 HTML 特殊字符（防止注入） */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

registerCommand({
  name: 'echo',
  descriptionKey: 'terminal.commands.echo.description',
  execute(args: string[]) {
    const text = args.map(stripQuotes).join(' ')
    return [HTML_MARKER + parseColorMarkers(text)]
  },
})
