/**
 * # 终端命令注册表
 *
 * FakeOS 终端命令的集中注册中心。
 * 每个命令模块在导入时通过 `registerCommand()` 注册自身。
 *
 * ## 命令接口
 *
 * ```ts
 * interface Command {
 *   name: string                    // 命令名
 *   descriptionKey: string          // 描述 i18n key
 *   usageKey?: string               // 用法 i18n key
 *   requiredPrivilege?: Privilege   // 所需权限（不设 = 所有人可用）
 *   execute: (args, ctx) => string[] // 执行函数
 * }
 * ```
 *
 * ## 为什么用 Map + 副作用导入注册
 *
 * - 简单：不需要动态导入或文件扫描
 * - 可扩展：新增命令只需创建文件 + import，自动注册
 * - 类型安全：`Command` 接口约束所有命令签名一致
 *
 * ## 权限设计
 *
 * `requiredPrivilege` 设为 'ADMIN' 的命令在 `LIMITED` 用户下返回拒绝访问。
 * 这与 FakeOS 的叙事设定一致：系统看起来能做事，但实际没权限。
 */

import type { PuzzleDescriptor } from '@/registries/puzzles'

/** 权限等级（与 desktopStore.privilegeClass 对应） */
export type Privilege = 'LIMITED' | 'ADMIN'

/** 命令执行上下文 */
export interface CommandContext {
  /** 当前登录用户 */
  user: string
  /** 权限等级 */
  privilegeClass: Privilege
  /**
   * i18n 翻译函数。
   * 命令模块在组件树外注册，无法使用 Vue 的 `useI18n()`，
   * 因此将翻译函数注入 context，命令通过此函数解析面向用户的文本。
   *
   * @param key - i18n key，如 'terminal.notFound'
   * @param params - 可选插值参数，如 `{ cmd: 'foo' }`
   * @returns 翻译后的字符串
   */
  t: (key: string, params?: Record<string, string>) => string
  /**
   * 打开谜题窗口（可选，由 Terminal.vue 注入）。
   * `sil` 命令通过此回调创建谜题窗口。
   *
   * @param puzzle - 谜题描述符
   * @returns true 表示窗口创建成功
   */
  openPuzzleWindow?: (puzzle: PuzzleDescriptor) => boolean
  /** 关闭当前终端窗口（可选，由 Terminal.vue 注入） */
  closeTerminal?: () => void
}

/** 单个命令的定义 */
export interface Command {
  /** 命令名（不含参数），如 'help' */
  name: string
  /** 简短描述（i18n key），如 'terminal.commands.help.description' */
  descriptionKey: string
  /** 使用说明（i18n key），可选 */
  usageKey?: string
  /** 所需最低权限，不设则所有用户可用 */
  requiredPrivilege?: Privilege
  /**
   * 执行命令。
   * @param args - 空格分割的参数列表
   * @param ctx - 命令上下文（用户、权限）
   * @returns 输出行数组。返回 `['__CLEAR__']` 表示清屏
   */
  execute: (args: string[], ctx: CommandContext) => string[]
}

/** 命令注册表 */
export const commandRegistry = new Map<string, Command>()

/**
 * 注册一个命令。
 * 通常在命令模块顶层调用，利用 import 副作用完成注册。
 *
 * @example
 * ```ts
 * registerCommand({
 *   name: 'help',
 *   descriptionKey: 'terminal.commands.help.description',
 *   execute: () => ['Available commands: ...'],
 * })
 * ```
 */
export function registerCommand(cmd: Command) {
  commandRegistry.set(cmd.name, cmd)
}
