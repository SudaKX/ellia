/**
 * # cat — 读取文件内容
 *
 * 基于统一文件系统（useFileSystem），读取文件文本内容并校验访问权限。
 *
 * ## 数据流
 *
 * ```
 * args[0] → 路径解析（绝对/相对） → getFileContent(path, player) → 输出
 *                                    ├─ 有权限 + 有内容 → 返回文本行
 *                                    ├─ 有权限 + 无内容 → "No such file"（如 .puz）
 *                                    └─ 无权限           → "PERMISSION DENIED"
 * ```
 *
 * ## 两阶段校验
 *
 * 1. **快速路径**：调用 `getFileContent(path, player)`，内部处理了节点查找 + accessRule 校验。
 *    如果返回非 null，直接输出。
 * 2. **权限区分**：如果返回 null，再通过 `resolveFileNode` 判断是"文件不存在"还是"权限不足"，
 *    以给出不同的错误提示。
 *
 * ## 已知的受限文件
 *
 * | 路径 | 规则 | 可见用户 |
 * |---|---|---|
 * | `/etc/shadow` | `accessRule: p => p.privilegeClass === 'ADMIN'` | ADMIN |
 * | `/home/PLAYER/notes.txt` | 父目录 `accessRule: p => p.currentAccount === 'PLAYER'` | PLAYER |
 *
 * @param args - args[0] 为文件路径（必填），支持相对路径（基于 cwd）和绝对路径
 * @param ctx  - 命令上下文，提供权限信息和 i18n 翻译函数
 * @returns 文件内容的行数组，或错误信息
 *
 * @example
 * ```
 * > cat readme.txt
 * Welcome to FakeOS. All actions are logged.
 *
 * > cat /etc/shadow
 * // PLAYER (LIMITED) →  "PERMISSION DENIED — this file requires elevated privileges."
 * // JDKTrigger (ADMIN) → "root:$6$ellia$XxXx..."
 * ```
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'
import { getFileContent, resolveFileNode, buildPlayerSnapshot } from '@/composables/useFileSystem'
import { useTerminalCwd } from '@/composables/useTerminalCwd'

registerCommand({
  name: 'cat',
  descriptionKey: 'terminal.commands.cat.description',
  execute(args: string[], _ctx: CommandContext) {
    const { getCwd } = useTerminalCwd()

    if (args.length === 0) {
      return ['cat: missing file operand']
    }

    const rawPath = args[0]
    // 将相对路径转换为绝对路径
    const filePath = rawPath.startsWith('/') ? rawPath : `${getCwd() === '/' ? '' : getCwd()}/${rawPath}`

    const player = buildPlayerSnapshot()

    // 第一层：尝试获取内容（内部已包含 accessRule 校验）
    const content = getFileContent(filePath, player)
    if (content !== null) {
      return content.split('\n')
    }

    // 第二层：区分"不存在"和"无权限"
    const node = resolveFileNode(filePath)
    if (node && node.type === 'file') {
      // 有 accessRule 且当前玩家不满足 → 权限不足
      if (node.accessRule && !node.accessRule(player)) {
        if (filePath === '/etc/shadow') {
          // 特殊叙事：shadow 文件有专属错误信息
          return ['PERMISSION DENIED — this file requires elevated privileges.']
        }
        return [`cat: ${rawPath}: PERMISSION DENIED — this file requires elevated privileges`]
      }
      // 文件存在但无内容（如 .puz 二进制文件）
      return [`cat: ${rawPath}: No such file or directory`]
    }

    return [`cat: ${rawPath}: No such file or directory`]
  },
})
