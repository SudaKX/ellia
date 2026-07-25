/**
 * # cat — 读取文件内容
 *
 * Mock 文件内容查询。根据路径返回对应文件的文本内容。
 * 管理员账户可读取 `/etc/shadow` 的真实内容（叙事暗示）。
 *
 * @example
 * ```
 * > cat readme.txt
 * Welcome to FakeOS. All actions are logged.
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'
import { useTerminalCwd } from '@/composables/useTerminalCwd'

/** Mock 文件内容映射：路径 → 文件内容 */
const mockFiles: Record<string, string> = {
  'readme.txt': 'Welcome to FakeOS. All actions are logged. Unauthorized access will be reported.',
  '/readme.txt': 'Welcome to FakeOS. All actions are logged. Unauthorized access will be reported.',
  '/sys/kernel.log': '[BOOT] FakeOS kernel initialized.\n[INFO] ElLInA daemon started.\n[WARN] Memory sector 0x07F corrupt — attempting recovery...\n[OK]   Recovery complete. 3 bad sectors isolated.',
  '/sys/cache/index.json': '{"version":1,"entries":[{"hash":"00a1b2c3","special_index":7}]}',
  '/tmp/readme.txt': 'Welcome to FakeOS. All actions are logged.',
  '/etc/shadow': 'root:$6$ellia$XxXxXxXxXxXxXxXxXxXxXxXxXxXxXx:19000:0:99999:7:::',
}

/** 受限文件：只有 ADMIN 用户可以读取实际内容 */
const restrictedFiles = new Set(['/etc/shadow', 'shadow', '/etc/hosts', 'hosts'])

registerCommand({
  name: 'cat',
  descriptionKey: 'terminal.commands.cat.description',
  execute(args: string[], ctx: CommandContext) {
    const { resolvePath, getCwd } = useTerminalCwd()

    if (args.length === 0) {
      return ['cat: missing file operand']
    }

    const rawPath = args[0]
    const filePath = rawPath.startsWith('/') ? rawPath : resolvePath(getCwd(), rawPath)
    const content = mockFiles[filePath]

    if (content === undefined) {
      const baseName = rawPath.replace(/^.*\//, '')
      if (restrictedFiles.has(filePath) || restrictedFiles.has(baseName)) {
        if (ctx.privilegeClass === 'ADMIN') {
          return [`cat: ${rawPath}: ACCESS GRANTED — but file is encrypted`]
        }
        return [`cat: ${rawPath}: PERMISSION DENIED — this file requires elevated privileges`]
      }
      return [`cat: ${rawPath}: No such file or directory`]
    }

    // ADMIN 读取 /etc/shadow 返回真实内容
    if (filePath === '/etc/shadow' && ctx.privilegeClass !== 'ADMIN') {
      return ['PERMISSION DENIED — this file requires elevated privileges.']
    }

    return content.split('\n')
  },
})
