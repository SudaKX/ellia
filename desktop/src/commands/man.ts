/**
 * # man — 查看命令手册
 *
 * 显示指定命令的详细用法。数据来源于命令注册表中的 `usageKey`。
 *
 * @example
 * ```
 * > man ls
 * NAME
 *   ls — 列出目录内容。
 *
 * USAGE
 *   ls [path]
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { commandRegistry, registerCommand } from '@/registries/commands'

registerCommand({
  name: 'man',
  descriptionKey: 'terminal.commands.man.description',
  usageKey: 'terminal.commands.man.usage',
  execute(args: string[], ctx: CommandContext): string[] {
    if (args.length === 0) {
      return [ctx.t('terminal.commands.man.noArg')]
    }

    const cmdName = args[0]
    const cmd = commandRegistry.get(cmdName)

    if (!cmd) {
      return [`man: ${cmdName}: ${ctx.t('terminal.notFound', { cmd: cmdName })}`]
    }

    const lines: string[] = [
      `NAME`,
      `  ${cmd.name} — ${ctx.t(cmd.descriptionKey)}`,
      '',
    ]

    if (cmd.usageKey) {
      lines.push('USAGE')
      lines.push(`  ${ctx.t(cmd.usageKey)}`)
    } else {
      lines.push('USAGE')
      lines.push(`  ${cmd.name}`)
    }

    if (cmd.requiredPrivilege) {
      lines.push('')
      lines.push(`PRIVILEGE REQUIRED: ${cmd.requiredPrivilege}`)
    }

    return lines
  },
})
