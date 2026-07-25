/**
 * # pwd — 打印当前工作目录
 *
 * 返回共享 cwd 状态的当前路径。
 *
 * @example
 * ```
 * > pwd
 * /home/PLAYER
 * ```
 */

import { registerCommand } from '@/registries/commands'
import { useTerminalCwd } from '@/composables/useTerminalCwd'

registerCommand({
  name: 'pwd',
  descriptionKey: 'terminal.commands.pwd.description',
  execute() {
    const { getCwd } = useTerminalCwd()
    return [getCwd()]
  },
})
