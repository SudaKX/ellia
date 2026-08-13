/**
 * # exit — 关闭终端窗口
 *
 * 通过 CommandContext 中的 closeTerminal 回调关闭当前终端窗口。
 * 无参数时正常退出，可带 status code（忽略）。
 *
 * @example
 * ```
 * > exit
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'

registerCommand({
  name: 'exit',
  descriptionKey: 'terminal.commands.exit.description',
  execute(_args: string[], ctx: CommandContext): string[] {
    ctx.closeTerminal?.()
    return []
  },
})
