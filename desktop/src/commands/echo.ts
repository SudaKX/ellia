/**
 * # echo — 回显文本
 *
 * 将参数拼接后直接输出。用于测试和脚本。
 *
 * @example
 * ```
 * > echo Hello World
 * Hello World
 * ```
 */

import { registerCommand } from '@/registries/commands'

registerCommand({
  name: 'echo',
  descriptionKey: 'terminal.commands.echo.description',
  execute(args: string[]) {
    return [args.join(' ')]
  },
})
