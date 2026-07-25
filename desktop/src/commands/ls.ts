/**
 * # ls — 列出目录内容
 *
 * Mock 文件树。根据参数路径列出文件和子目录。
 * 文件树结构设计为为后续谜题做铺垫（隐藏的 cache 目录、readme 文件等）。
 *
 * ## 目录结构（mock）
 *
 * ```
 * /
 * ├─ bin/        — 系统可执行文件（受限访问）
 * ├─ etc/        — 配置文件（受限访问）
 * ├─ home/
 * │   └─ PLAYER/ — PLAYER 用户主目录
 * ├─ sys/        — 系统目录（受限访问）
 * ├─ tmp/        — 临时文件
 * └─ readme.txt  — 欢迎文件
 * ```
 *
 * @example
 * ```
 * > ls
 * bin/  etc/  home/  sys/  tmp/  readme.txt
 * ```
 *
 * @param args - 路径参数，如 `ls /sys`
 */

import type { CommandContext } from '@/registries/commands'
import { registerCommand } from '@/registries/commands'
import { useTerminalCwd } from '@/composables/useTerminalCwd'

interface FileEntry {
  name: string
  type: 'dir' | 'file'
  /** 子目录内容（仅 dir 类型） */
  children?: FileEntry[]
}

/** Mock 根目录文件树 */
const rootDir: FileEntry[] = [
  { name: 'bin', type: 'dir', children: [
    { name: 'ellia_daemon', type: 'file' },
    { name: 'init', type: 'file' },
  ]},
  { name: 'etc', type: 'dir', children: [
    { name: 'hosts', type: 'file' },
    { name: 'shadow', type: 'file' },
  ]},
  { name: 'home', type: 'dir', children: [
    { name: 'PLAYER', type: 'dir', children: [
      { name: 'notes.txt', type: 'file' },
    ]},
  ]},
  { name: 'sys', type: 'dir', children: [
    { name: 'kernel.log', type: 'file' },
    { name: 'cache', type: 'dir', children: [
      { name: '00a1b2c3', type: 'file' },
      { name: 'index.json', type: 'file' },
    ]},
  ]},
  { name: 'tmp', type: 'dir', children: []},
  { name: 'readme.txt', type: 'file' },
  { name: 'puzzles', type: 'dir', children: [
    { name: 'caesar-cipher.puz', type: 'file' },
  ]},
]

/**
 * 解析路径为文件树节点数组。
 * 从根目录开始，逐段查找。不做 `..`、`.` 等特殊路径处理。
 * 导出供 `cd` 命令复用同一文件树进行路径校验。
 */
export function resolvePath(pathStr: string): FileEntry[] | null {
  if (pathStr === '/' || pathStr === '') return rootDir

  const segments = pathStr.replace(/^\//, '').split('/')
  let current: FileEntry[] = rootDir

  for (const seg of segments) {
    const found = current.find((e) => e.name === seg)
    if (!found) return null
    if (found.type !== 'dir') return null
    current = found.children!
  }

  return current
}

registerCommand({
  name: 'ls',
  descriptionKey: 'terminal.commands.ls.description',
  execute(args: string[], ctx: CommandContext) {
    const { getCwd } = useTerminalCwd()
    const pathStr = args[0] || getCwd()
    const entries = resolvePath(pathStr)

    if (entries === null) {
      return [`ls: ${pathStr}: No such file or directory`]
    }

    if (entries.length === 0) {
      return ['(empty)']
    }

    // 目录用 / 后缀，文件不加
    const names = entries.map((e) => (e.type === 'dir' ? `${e.name}/` : e.name))
    return [names.join('  ')]
  },
})
