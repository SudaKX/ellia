/**
 * # sudo — 权限拒绝叙事
 *
 * 不论传入什么参数，始终返回 PERMISSION DENIED。
 * 这是 FakeOS 世界观的核心叙事机制：系统看起来功能齐全，
 * 但 LIMITED 用户没有提权能力。
 *
 * 有趣的是 sudo 命令本身在 help 中可见（因为 requiredPrivilege='ADMIN'
 * 而当前用户是 LIMITED，权限检查在 Terminal.vue 路由层拦截），
 * 给了玩家一种"我或许能做什么"的错觉。
 *
 * ## i18n
 *
 * 被拒信息通过 `ctx.t('terminal.sudo.denied')` 获取，
 * 语言跟随系统设置自动切换。
 *
 * @example
 * ```
 * > sudo ls
 * sudo: PERMISSION DENIED — administrator privileges required
 *
 * > sudo cat /etc/shadow
 * sudo: PERMISSION DENIED — administrator privileges required
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'

registerCommand({
  name: 'sudo',
  descriptionKey: 'terminal.commands.sudo.description',
  requiredPrivilege: 'ADMIN',
  execute(_args: string[], ctx: CommandContext) {
    // 权限检查在 Terminal.vue 的路由层完成，正常情况下 LIMITED 用户不会进入这里。
    // 但如果未来开放 ADMIN 用户，这里可以扩展实际提权逻辑。
    return [ctx.t('terminal.sudo.denied')]
  },
})
