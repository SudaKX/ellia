/**
 * # cat — 读取文件内容
 *
 * Mock 文件内容查询。根据路径返回对应文件的文本内容。
 * 文件不存在或为目录时返回错误提示。
 * 后续后端接入后，替换 execute 函数中的 mock 数据即可。
 *
 * @example
 * ```
 * > cat readme.txt
 * Welcome to FakeOS. All actions are logged.
 * ```
 *
 * @param args - 文件路径，如 `cat readme.txt` 或 `cat /sys/kernel.log`
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'

/** Mock 文件内容映射：路径 → 文件内容 */
const mockFiles: Record<string, string> = {
  'readme.txt': 'Welcome to FakeOS. All actions are logged. Unauthorized access will be reported.',
  '/readme.txt': 'Welcome to FakeOS. All actions are logged. Unauthorized access will be reported.',
  '/sys/kernel.log': '[BOOT] FakeOS kernel initialized.\n[INFO] ElLInA daemon started.\n[WARN] Memory sector 0x07F corrupt — attempting recovery...\n[OK]   Recovery complete. 3 bad sectors isolated.',
  '/sys/cache/index.json': '{"version":1,"entries":[{"hash":"00a1b2c3","special_index":7}]}',
  '/tmp/readme.txt': 'Welcome to FakeOS. All actions are logged.',
  '/etc/shadow': 'PERMISSION DENIED — this file requires elevated privileges.',
}

registerCommand({
  name: 'cat',
  descriptionKey: 'terminal.commands.cat.description',
  execute(args: string[], ctx: CommandContext) {
    if (args.length === 0) {
      return ['cat: missing file operand']
    }

    const filePath = args[0]
    const content = mockFiles[filePath]

    if (content === undefined) {
      return [`cat: ${filePath}: No such file or directory`]
    }

    return content.split('\n')
  },
})
