/**
 * # pwd — 打印当前工作目录
 *
 * 模拟 Unix pwd 命令。当前使用 mock 路径，
 * 后端接入后可根据实际虚拟文件系统返回。
 *
 * @example
 * ```
 * > pwd
 * /home/PLAYER
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'

registerCommand({
  name: 'pwd',
  descriptionKey: 'terminal.commands.pwd.description',
  execute(_args: string[], ctx: CommandContext) {
    // 不同用户有不同的 home 目录
    return [`/home/${ctx.user}`]
  },
})
