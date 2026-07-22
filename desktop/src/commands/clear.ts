/**
 * # clear — 清屏
 *
 * 返回特殊标记 `__CLEAR__`，由 Terminal.vue 检测并清空输出缓冲区。
 * 命令函数不直接操作 DOM 或组件状态，保持职责分离。
 *
 * @example
 * ```
 * > clear
 * （终端清空）
 * ```
 */

import { registerCommand } from '@/registries/commands'

/** 清屏标记，Terminal.vue 检测到此返回值时清空 lines 数组 */
export const CLEAR_MARKER = '__CLEAR__'

registerCommand({
  name: 'clear',
  descriptionKey: 'terminal.commands.clear.description',
  execute() {
    return [CLEAR_MARKER]
  },
})
