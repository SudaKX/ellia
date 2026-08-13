/**
 * # date — 显示系统时间
 *
 * 输出当前日期和时间（ISO 格式）。
 *
 * @example
 * ```
 * > date
 * 2026-07-21T15:30:00.000Z
 * ```
 */

import { registerCommand } from '@/registries/commands'

registerCommand({
  name: 'date',
  descriptionKey: 'terminal.commands.date.description',
  execute() {
    return [new Date().toISOString()]
  },
})
