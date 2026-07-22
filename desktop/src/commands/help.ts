/**
 * # help — 列出可用命令
 *
 * 遍历命令注册表，按当前用户权限过滤，格式化输出命令列表。
 * 权限不足的命令不显示（不给玩家暗示存在高权限命令）。
 *
 * ## i18n 处理
 *
 * 命令描述存储在 `cmd.descriptionKey` 中（如 `'terminal.commands.help.description'`），
 * 通过 `ctx.t()` 在运行时翻译，语言自动跟随系统设置。
 *
 * @example
 * ```
 * > help
 * Available commands:
 *   help       — List available commands.
 *   whoami     — Display current user identity.
 *   ...
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { commandRegistry, registerCommand } from '@/registries/commands'

registerCommand({
  name: 'help',
  descriptionKey: 'terminal.commands.help.description',
  execute(_args: string[], ctx: CommandContext): string[] {
    const lines: string[] = ['Available commands:']

    for (const [, cmd] of commandRegistry) {
      // 权限过滤：不向低权限用户展示高权限命令的存在
      if (cmd.requiredPrivilege === 'ADMIN' && ctx.privilegeClass !== 'ADMIN') continue

      // 命令名左对齐到 10 字符宽度，形成整齐的列
      const padded = cmd.name.padEnd(10)
      // 通过 ctx.t() 翻译描述文本
      const translated = ctx.t(cmd.descriptionKey)
      lines.push(`  ${padded}— ${translated}`)
    }

    return lines
  },
})
