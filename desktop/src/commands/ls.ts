/**
 * # ls — 列出目录内容
 *
 * 基于统一文件系统（useFileSystem），列出指定目录下的可见文件和子目录。
 *
 * ## 数据流
 *
 * ```
 * args[0] → resolvePath(path) → FileNode[] → getVisibleChildren(nodes, playerSnapshot) → 输出
 * ```
 *
 * 无参数时默认使用根目录 `/`，而非当前工作目录（cwd）。
 * 这是有意为之：ls 的默认行为是列出当前目录，但为了与 ls 命令的传统行为一致，
 * 以及避免 cwd 可能为不存在路径的边界情况，这里使用根目录作为 fallback。
 *
 * ## 访问控制
 *
 * 通过 `getVisibleChildren` 自动过滤不可见内容：
 * - `/etc/shadow` 仅 ADMIN 可见
 * - `/home/PLAYER/` 仅 PLAYER 账户可见
 * - 无可见后代的空目录会被隐藏
 *
 * ## 文件树结构
 *
 * ```
 * /
 * ├── bin/        — 系统可执行文件
 * ├── etc/        — 配置文件
 * ├── home/       — 用户主目录
 * ├── sys/        — 系统目录
 * ├── tmp/        — 临时文件
 * ├── puzzles/    — 谜题文件
 * └── readme.txt  — 欢迎文件
 * ```
 *
 * @param args  - args[0] 为目标路径，可选（不传 = 列出根目录）
 * @param _ctx  - 命令上下文（未使用，权限判断由 useFileSystem 内部处理）
 * @returns 输出行数组，每行是用空格分隔的文件/目录名列表
 *
 * @example
 * ```
 * > ls
 * bin/  etc/  home/  sys/  tmp/  puzzles/  readme.txt
 *
 * > ls /etc
 * hosts  shadow
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'
import { getVisibleChildren, buildPlayerSnapshot, resolvePath } from '@/composables/useFileSystem'
import { useTerminalCwd } from '@/composables/useTerminalCwd'

registerCommand({
  name: 'ls',
  descriptionKey: 'terminal.commands.ls.description',
  execute(args: string[], _ctx: CommandContext): string[] {
    const pathStr = args[0]
    // 未指定路径时列出当前工作目录
    const entries = pathStr ? resolvePath(pathStr) : resolvePath(useTerminalCwd().getCwd())

    if (entries === null) {
      return [`ls: ${pathStr}: No such file or directory`]
    }

    // 从 Pinia store 获取当前玩家状态，过滤不可见节点
    const player = buildPlayerSnapshot()
    const visible = getVisibleChildren(entries, player)

    if (visible.length === 0) {
      return ['(empty)']
    }

    // 目录加 / 后缀，文件不加
    const names = visible.map((e) => (e.type === 'dir' ? `${e.name}/` : e.name))
    return [names.join('  ')]
  },
})
