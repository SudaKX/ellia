/**
 * # sil — 谜题加载器
 *
 * 终端命令，用于打开谜题窗口。
 *
 * ## 用法
 *
 * ```
 * > sil <puzzle_id>
 * ```
 *
 * 执行后，会在桌面上打开一个对应谜题的窗口。
 * 如果 puzzle_id 不存在，返回提示信息。
 *
 * ## 实现原理
 *
 * `sil` 命令通过 `CommandContext.openPuzzleWindow` 回调创建窗口。
 * 该回调由 Terminal.vue 在构建 context 时注入，底层通过
 * `windowService.send({ type: 'create-window' })` 动态创建谜题窗口。
 *
 * ## 为什么命令叫 "sil"
 *
 * "sil" 是谜题系统的入口命令名，简短好记。
 * 文件名 `sil.ts` 与命令名一致，通过副作用 import 自动注册。
 *
 * @example
 * ```
 * > sil caesar-cipher
 * Opening puzzle: caesar-cipher ...
 * （桌面出现谜题窗口）
 *
 * > sil unknown-puzzle
 * Puzzle not found: unknown-puzzle
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'
import { puzzleRegistry } from '@/registries/puzzles'

registerCommand({
  name: 'sil',
  descriptionKey: 'terminal.commands.sil.description',
  execute(args: string[], ctx: CommandContext) {
    if (args.length === 0) {
      // 列出所有可用谜题
      const ids = Array.from(puzzleRegistry.keys())
      if (ids.length === 0) {
        return ['No puzzles registered.']
      }
      // 只显示谜题 ID 列表
      return ['Available puzzles:', ...ids.map((id) => `  - ${id}`)]
    }

    const puzzleId = args[0]
    const puzzle = puzzleRegistry.get(puzzleId)

    if (!puzzle) {
      return [`sil: puzzle not found: "${puzzleId}"`]
    }

    // 通过 context 中的回调创建谜题窗口
    if (ctx.openPuzzleWindow) {
      const success = ctx.openPuzzleWindow(puzzle)
      if (success) {
        return [`Opening puzzle: ${puzzleId} ...`]
      }
      return [`sil: failed to open puzzle "${puzzleId}"`]
    }

    // 如果 openPuzzleWindow 未提供（非终端环境），给出提示
    return [`sil: this command must be run from the terminal.`]
  },
})
