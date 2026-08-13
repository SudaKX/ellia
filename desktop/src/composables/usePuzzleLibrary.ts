/**
 * # usePuzzleLibrary — 题目库（内置 + 远程发布）
 *
 * 数据驱动题目的统一数据源：
 * - 内置题库：desktop/src/puzzles/data/*.ts（游戏自带的题，如 caesar-cipher）
 * - 远程发布：出题器（desktop_designer）审核通过后导出的 published-questions.json，
 *   通过 loadPublishedPuzzles() 拉取并注册进 puzzleRegistry（"自动发现"）
 *
 * ## 职责分工
 *
 * - `getPuzzleDefinition(id)`：PuzzlePlayer 按 id 取定义（内置优先，远程兜底）
 * - `loadPublishedPuzzles()`：启动时调用一次（fire-and-forget），开关
 *   USE_PUBLISHED_QUESTIONS 控制，失败/关闭时静默（不影响现有内置谜题）
 *
 * ## 为什么模块级 Map 而非 Pinia
 *
 * 与 useFileSystem 一致：题库在应用生命周期内基本静态（内置常量 + 启动时拉取一次），
 * 不需要响应式追踪；PuzzlePlayer 按 id 同步读取即可。
 */

import { defineAsyncComponent } from 'vue'

import { PUBLISHED_QUESTIONS_URL, USE_PUBLISHED_QUESTIONS } from '@/config/api'
import { puzzleRegistry } from '@/registries/puzzles'
import { CAESAR_DEFINITION } from '@/puzzles/data/caesar'
import type { PuzzleDefinition } from '@/types/puzzle'

/** 内置题库（应用自带） */
const builtinDefinitions: PuzzleDefinition[] = [CAESAR_DEFINITION]

/** 远程拉取的已发布题库（id → definition） */
const remoteDefinitions = new Map<string, PuzzleDefinition>()

/** 通用播放器（延迟加载，避免与 PuzzlePlayer 的 import 循环） */
const PuzzlePlayer = defineAsyncComponent(() => import('@/components/puzzles/PuzzlePlayer.vue'))

/**
 * 按 id 取题目定义（内置优先，远程兜底）。
 *
 * @param puzzleId - 题目 id（.puz 文件名 / sil 参数）
 * @returns 题目定义，未找到返回 null
 */
export function getPuzzleDefinition(puzzleId: string): PuzzleDefinition | null {
  const builtin = builtinDefinitions.find((definition) => definition.id === puzzleId)
  if (builtin) return builtin
  return remoteDefinitions.get(puzzleId) ?? null
}

/**
 * 拉取出题器发布的已审核题目并注册进谜题注册表。
 *
 * 仅当 USE_PUBLISHED_QUESTIONS 为 true 时执行；任何失败（网络/格式）静默忽略，
 * 保证不干扰现有内置谜题。
 * 由 DesktopView setup 调用一次（fire-and-forget）。
 */
export async function loadPublishedPuzzles(): Promise<void> {
  if (!USE_PUBLISHED_QUESTIONS) return

  try {
    const response = await fetch(PUBLISHED_QUESTIONS_URL)
    if (!response.ok) return
    const data = (await response.json()) as { questions?: PuzzleDefinition[] }
    for (const definition of data.questions ?? []) {
      if (!definition.id || definition.id === '') continue
      remoteDefinitions.set(definition.id, definition)
      puzzleRegistry.set(definition.id, {
        id: definition.id,
        nameKey: 'puzzles.label',
        descriptionKey: 'puzzles.label',
        component: PuzzlePlayer,
        definition,
        defaultWidth: 560,
        defaultHeight: 440,
        resizable: true,
      })
    }
  } catch {
    // 静默：远程题库不可达时不影响游戏启动
  }
}
