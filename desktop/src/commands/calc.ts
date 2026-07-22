/**
 * # calc — 算术计算器
 *
 * 支持 JavaScript 全量算术运算符的终端计算器。
 * 同时导出 `evaluateExpression()` 供 Terminal.vue 自动识别数学表达式。
 *
 * ## 支持的运算符
 *
 * | 运算符 | 说明     | 示例          |
 * |--------|----------|---------------|
 * | `+`    | 加法     | `2 + 3` → 5   |
 * | `-`    | 减法     | `5 - 2` → 3   |
 * | `*`    | 乘法     | `3 * 4` → 12  |
 * | `/`    | 除法     | `10 / 3` → 3.333... |
 * | `%`    | 取余     | `10 % 3` → 1  |
 * | `**`   | 幂运算   | `2 ** 10` → 1024 |
 * | `()`   | 分组     | `(2+3)*4` → 20 |
 *
 * ## 支持的 Math 函数
 *
 * `Math.PI`, `Math.E`, `Math.sqrt(x)`, `Math.abs(x)`, `Math.sin(x)`,
 * `Math.cos(x)`, `Math.tan(x)`, `Math.log(x)`, `Math.log2(x)`,
 * `Math.log10(x)`, `Math.exp(x)`, `Math.floor(x)`, `Math.ceil(x)`,
 * `Math.round(x)`, `Math.pow(x,y)`, `Math.min(a,b,...)`, `Math.max(a,b,...)`,
 * `Math.random()`
 *
 * ## 安全设计
 *
 * 使用正则校验输入，仅允许数字、运算符、括号、小数点和 `Math.` 前缀，
 * 拒绝任何可能注入代码的字符。校验通过后才用 `new Function()` 求值。
 *
 * @example
 * ```
 * > calc 1 + 2 * 3
 * 7
 *
 * > 1 + 2 * 3        （Terminal.vue 自动识别为数学表达式）
 * 7
 * ```
 */

import { registerCommand } from '@/registries/commands'

/**
 * 安全校验：只允许算术运算相关字符。
 * - 纯数字/运算符表达式
 * - 含 Math.* 函数调用的表达式
 */
const SAFE_EXPR_RE = /^[\d+\-*/%().eE,\s]+$|^[\d+\-*/%().eE,\s]*Math\.[\w+\-*/%().,\s]+$/

/**
 * 判断整个输入字符串是否是一个合法的算术表达式。
 * 用于 Terminal.vue 在命令未找到时自动回退求值。
 *
 * 识别条件：输入以数字、`(`、`-`、`+`、`Math.` 开头。
 * 这样 `help`、`ls` 等正常命令不会被误判。
 *
 * @param raw - 用户原始输入（trim 后）
 * @returns 是否是数学表达式
 */
export function isMathExpression(raw: string): boolean {
  // 必须看起来像表达式：以数字/(/Math./+/- 开头（- 和 + 可能是正负号）
  if (!/^[\d(]|^Math\.|^[+\-]\d|^[+\-]\(/.test(raw)) return false

  // 宽松化空格后做安全校验
  const normalized = raw.replace(/\s+/g, ' ')
  return SAFE_EXPR_RE.test(normalized)
}

/**
 * 求值一个已验证安全的算术表达式。
 * 调用前应先用 `isMathExpression()` 校验。
 *
 * @param expr - 算术表达式字符串
 * @returns 求值结果的字符串表示，或错误信息
 */
export function evaluateExpression(expr: string): string {
  try {
    const result = new Function(`return (${expr})`)()
    return String(result)
  } catch (err) {
    return `Error: ${(err as Error).message}`
  }
}

registerCommand({
  name: 'calc',
  descriptionKey: 'terminal.commands.calc.description',
  execute(args: string[]) {
    if (args.length === 0) {
      return ['calc: missing expression. Usage: calc <expression>']
    }

    const expr = args.join(' ')

    if (!isMathExpression(expr)) {
      return ['calc: invalid expression — only arithmetic operators and Math.* functions are allowed']
    }

    return [evaluateExpression(expr)]
  },
})
