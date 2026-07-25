/**
 * # cd — 切换当前工作目录
 *
 * 两步校验流程：
 * 1. 通过 `useTerminalCwd.resolvePath()` 将用户输入解析为绝对路径（处理 `.`、`..`、`~`）
 * 2. 通过 `useFileSystem.resolvePath()` 在文件树中校验路径是否存在且为目录
 *
 * 两步校验都在各自模块中完成，cd 命令只负责编排调用顺序。
 *
 * ## 特殊处理
 *
 * | 输入 | 行为 |
 * |---|---|
 * | 无参数 / `~` | 跳转到 `/home/PLAYER` |
 * | `..` | 返回上级目录（由 useTerminalCwd.resolvePath 处理） |
 * | 相对路径 | 基于当前 cwd 拼接（由 useTerminalCwd 处理） |
 * | 绝对路径 | 直接传递给 useFileSystem 校验 |
 *
 * ## 依赖关系
 *
 * ```
 * cd 命令
 *   ├─ useTerminalCwd.resolvePath()  → 纯字符串路径解析（处理 .././ 符号链接）
 *   └─ useFileSystem.resolvePath()   → 文件树中存在性校验
 * ```
 *
 * @param args - args[0] 为目标目录（可选）
 * @param _ctx - 命令上下文（未使用）
 * @returns 空数组（成功时静默），或错误信息
 *
 * @example
 * ```
 * > cd /sys
 * > pwd
 * /sys
 * > cd ..
 * > pwd
 * /
 * > cd ~
 * > pwd
 * /home/PLAYER
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'
import { resolvePath } from '@/composables/useFileSystem'
import { useTerminalCwd } from '@/composables/useTerminalCwd'

registerCommand({
  name: 'cd',
  descriptionKey: 'terminal.commands.cd.description',
  usageKey: 'terminal.commands.cd.usage',
  execute(args: string[], _ctx: CommandContext): string[] {
    const { resolvePath: resolveCwd, setCwd, getCwd } = useTerminalCwd()

    // 无参数或 ~ → 返回家目录
    if (args.length === 0 || args[0] === '~') {
      setCwd('/home/PLAYER')
      return []
    }

    // 第一步：纯字符串路径解析（处理 .././ 等）
    const target = resolveCwd(getCwd(), args[0])

    // 第二步：在文件树中校验路径存在性
    const entries = resolvePath(target)

    if (entries === null) {
      return [`cd: ${args[0]}: No such file or directory`]
    }

    // 校验通过，更新共享 cwd 状态
    setCwd(target)
    return []
  },
})
