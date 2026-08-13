/**
 * # 谜题注册入口
 *
 * 本文件通过副作用 import 注册所有谜题。
 * 在应用入口（DesktopView.vue）中 import 本文件即可触发注册。
 *
 * ## 数据驱动题目注册方式
 *
 * 内置题以 PuzzleDefinition（types/puzzle.ts）定义在 `src/puzzles/data/` 下，
 * 统一由通用播放器 PuzzlePlayer 渲染：
 *
 * ```ts
 * registerPuzzle({
 *   id: definition.id,
 *   nameKey: 'puzzles.<id>.title',      // 兜底 i18n key（definition.title 优先）
 *   descriptionKey: 'puzzles.<id>.description',
 *   component: PuzzlePlayer,
 *   definition,                          // 数据驱动定义
 *   defaultWidth: 520,
 *   defaultHeight: 400,
 * })
 * ```
 *
 * 出题器（desktop_designer）审核发布的题目由 usePuzzleLibrary.loadPublishedPuzzles()
 * 动态注册（无需在此手写），开关见 config/api.ts 的 USE_PUBLISHED_QUESTIONS。
 *
 * @example
 * ```ts
 * registerPuzzle({
 *   id: 'my-puzzle',
 *   nameKey: 'puzzles.myPuzzle.title',
 *   descriptionKey: 'puzzles.myPuzzle.description',
 *   component: defineAsyncComponent(() => import('@/components/puzzles/MyPuzzle.vue')),
 *   defaultWidth: 600,
 *   defaultHeight: 400,
 * })
 * ```
 */

import { defineAsyncComponent } from 'vue'

import { CAESAR_DEFINITION } from '@/puzzles/data/caesar'
import { registerPuzzle } from '@/registries/puzzles'

/** 通用题目播放器（数据驱动题统一渲染入口） */
const PuzzlePlayer = defineAsyncComponent(() => import('@/components/puzzles/PuzzlePlayer.vue'))

registerPuzzle({
  id: CAESAR_DEFINITION.id,
  nameKey: 'puzzles.caesarCipher.title',
  descriptionKey: 'puzzles.caesarCipher.description',
  component: PuzzlePlayer,
  definition: CAESAR_DEFINITION,
  defaultWidth: 520,
  defaultHeight: 400,
})
