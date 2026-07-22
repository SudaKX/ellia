/**
 * # uname — 系统信息
 *
 * 模拟 Unix uname 命令，显示 FakeOS 内核版本。
 * 输出中包含当前语言环境下的系统名称和架构。
 *
 * @example
 * ```
 * > uname
 * FakeOS ellia-kernel 1.0.0 #1 SMP 2026-07-21 x64
 * ```
 */

import { registerCommand } from '@/registries/commands'

registerCommand({
  name: 'uname',
  descriptionKey: 'terminal.commands.uname.description',
  execute() {
    const now = new Date()
    const date = now.toISOString().split('T')[0]
    // 架构硬编码为 x64（FakeOS 设定）
    return [`FakeOS ellia-kernel 1.0.1 #1 SMP ${date} x64`]
  },
})
