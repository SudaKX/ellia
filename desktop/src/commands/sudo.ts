/**
 * # sudo — 权限提升
 *
 * LIMITED 用户：返回权限拒绝叙事（FakeOS 核心设定——无法提权）。
 * ADMIN 用户：提示已是最高权限。
 *
 * @example
 * ```
 * > sudo rm -rf /
 * sudo: PERMISSION DENIED — administrator privileges required
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'

registerCommand({
  name: 'sudo',
  descriptionKey: 'terminal.commands.sudo.description',
  requiredPrivilege: 'ADMIN',
  execute(_args: string[], ctx: CommandContext): string[] {
    if (ctx.privilegeClass === 'ADMIN') {
      return ['sudo: You are already root.']
    }
    return [ctx.t('terminal.sudo.denied')]
  },
})
