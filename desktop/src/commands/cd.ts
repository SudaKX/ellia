/**
 * # cd — 切换当前工作目录
 *
 * 基于 mock 文件树（与 `ls` 共享同一结构），校验路径后更新共享 cwd 状态。
 *
 * @example
 * ```
 * > cd /sys
 * > pwd
 * /sys
 * > cd ..
 * > pwd
 * /
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'
import { resolvePath as resolveLsPath } from '@/commands/ls'
import { useTerminalCwd } from '@/composables/useTerminalCwd'

registerCommand({
  name: 'cd',
  descriptionKey: 'terminal.commands.cd.description',
  usageKey: 'terminal.commands.cd.usage',
  execute(args: string[], _ctx: CommandContext): string[] {
    const { resolvePath, setCwd, getCwd } = useTerminalCwd()

    if (args.length === 0 || args[0] === '~') {
      setCwd('/home/PLAYER')
      return []
    }

    const target = resolvePath(getCwd(), args[0])
    const entries = resolveLsPath(target)

    if (entries === null) {
      return [`cd: ${args[0]}: No such file or directory`]
    }

    setCwd(target)
    return []
  },
})
