/**
 * # 谜题注册表 (Puzzle Registry)
 *
 * FakeOS 谜题系统的集中注册中心。
 * 谜题开发者通过 `registerPuzzle()` 注册谜题，终端用户通过 `sil <id>` 命令打开。
 *
 * ## 谜题开发者 API
 *
 * ```ts
 * // 1. 创建谜题组件（Vue SFC）
 * // 2. 在 puzzle 注册文件中调用 registerPuzzle()
 * registerPuzzle({
 *   id: 'caesar-cipher',                  // 唯一标识，sil 命令的参数
 *   nameKey: 'puzzles.caesar-cipher.name', // i18n key：谜题名称
 *   descriptionKey: 'puzzles.caesar-cipher.description', // i18n key：简短描述
 *   component: defineAsyncComponent(() => import('@/components/puzzles/CaesarCipher.vue')),
 *   defaultWidth: 600,
 *   defaultHeight: 400,
 * })
 * ```
 *
 * ## 谜题组件中使用 usePuzzle()
 *
 * ```ts
 * const { state, submitAnswer, requestHint, hints } = usePuzzle('caesar-cipher')
 * ```
 *
 * ## 为什么谜题不用 ApplicationId 注册
 *
 * 谜题不在 Launchpad 和 DockBar 中展示，不需要 `icon`、`groupKey` 等应用元数据。
 * 谜题数量可能很多（数十个），独立注册表避免污染应用注册表。
 * 谜题窗口通过 `windowService.send()` 动态创建，不走 `windowService.open()` 的单例逻辑。
 *
 * ## 与 darksky 分支区别
 *
 * darksky 分支无谜题系统。本分支独立实现完整的谜题框架。
 */

import type { Component } from 'vue'

/** 谜题描述符——开发者注册谜题时需要提供的信息 */
export interface PuzzleDescriptor {
  /** 唯一标识，用作 `sil <id>` 命令的参数 */
  id: string
  /** 谜题名称 i18n key */
  nameKey: string
  /** 谜题描述 i18n key */
  descriptionKey: string
  /** 谜题 Vue 组件 */
  component: Component
  /** 窗口默认宽度（px） */
  defaultWidth: number
  /** 窗口默认高度（px） */
  defaultHeight: number
  /** 是否允许调整窗口大小（默认 true） */
  resizable?: boolean
}

/** 全局谜题注册表 */
export const puzzleRegistry = new Map<string, PuzzleDescriptor>()

/**
 * 注册一个谜题。
 * 谜题开发者应在 puzzle 注册文件中调用此函数，
 * 然后该注册文件应在应用入口被 import（触发副作用注册）。
 *
 * @param puzzle - 谜题描述符
 *
 * @example
 * ```ts
 * registerPuzzle({
 *   id: 'caesar-cipher',
 *   nameKey: 'puzzles.caesar-cipher.name',
 *   descriptionKey: 'puzzles.caesar-cipher.description',
 *   component: defineAsyncComponent(() => import('@/components/puzzles/CaesarCipher.vue')),
 *   defaultWidth: 600,
 *   defaultHeight: 400,
 * })
 * ```
 */
export function registerPuzzle(puzzle: PuzzleDescriptor): void {
  if (puzzleRegistry.has(puzzle.id)) {
    // console.warn(`[PuzzleRegistry] Puzzle "${puzzle.id}" is already registered. Overwriting.`)
  }
  puzzleRegistry.set(puzzle.id, puzzle)
}

/**
 * 获取所有已注册谜题的 ID 列表。
 * 供 FileExplorer 列出可用谜题文件。
 */
export function getPuzzleIds(): string[] {
  return Array.from(puzzleRegistry.keys())
}
