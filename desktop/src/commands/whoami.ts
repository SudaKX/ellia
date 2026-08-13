/**
 * # whoami — 显示当前用户身份
 *
 * 格式与状态栏一致：PRIVILEGE:USERNAME
 * 帮助玩家确认当前登录的是 PLAYER 还是 JDKTrigger。
 *
 * @example
 * ```
 * > whoami
 * LIMITED:PLAYER
 * ```
 */

import { registerCommand } from '@/registries/commands'

registerCommand({
  name: 'whoami',
  descriptionKey: 'terminal.commands.whoami.description',
  execute(_args: string[], ctx) {
    return [`${ctx.privilegeClass}:${ctx.user}`]
  },
})
