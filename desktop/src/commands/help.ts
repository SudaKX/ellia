/**
 * # help — 列出可用命令
 *
 * 遍历命令注册表，按当前用户权限过滤：
 * - ADMIN 用户可见全部命令（包括高权限命令列表）
 * - LIMITED 用户不展示需要 ADMIN 权限的命令
 *
 * @example
 * ```
 * > help
 * Available commands:
 *   help       — 列出可用命令。
 *   whoami     — 显示当前用户身份。
 *   ...
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { commandRegistry, registerCommand } from '@/registries/commands'

registerCommand({
  name: 'help',
  descriptionKey: 'terminal.commands.help.description',
  execute(_args: string[], ctx: CommandContext): string[] {
    const isAdmin = ctx.privilegeClass === 'ADMIN'
    const lines: string[] = [isAdmin ? 'All commands (ADMIN):' : 'Available commands:']

    for (const [, cmd] of commandRegistry) {
      // 权限过滤：不向低权限用户展示高权限命令
      if (cmd.requiredPrivilege === 'ADMIN' && !isAdmin) continue

      const padded = cmd.name.padEnd(10)
      const translated = ctx.t(cmd.descriptionKey)
      lines.push(`  ${padded}— ${translated}`)
    }

    if (!isAdmin) {
      lines.push('')
      lines.push(`Use "man <command>" for detailed usage.`)
    }

    return lines
  },
})
