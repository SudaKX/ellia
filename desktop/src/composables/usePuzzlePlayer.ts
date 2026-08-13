/**
 * # usePuzzlePlayer — 通用题目（数据驱动）校验与状态
 *
 * PuzzlePlayer.vue 的运行时 API：多题型答案校验 + solved 状态持久化。
 * 与 usePuzzle（旧单文本谜题 API）并行存在，互不影响：
 * - usePuzzle：旧谜题组件（如 ExampleCipher 兼容）用
 * - usePuzzlePlayer：数据驱动题目（PuzzleDefinition）用
 *
 * ## 校验规则
 *
 * - `single`：恰选 1 项，且该项 correct
 * - `multi`：所选集合与正确集合全等（顺序无关）
 * - `fill`：每个空 trim 后与 fillAnswers[i] 大小写不敏感比较
 *
 * ## solved 持久化
 *
 * 沿用 usePuzzle 的 localStorage 语义：key `ellia.puzzle.{id}`，值为 'solved'。
 * 与旧谜题共用同一命名空间，保证"解过一次"在全游戏一致。
 */

import type { PuzzleDefinition } from '@/types/puzzle'

/** localStorage key 前缀（与 usePuzzle 保持一致） */
const STORAGE_PREFIX = 'ellia.puzzle.'

/** 是否已解决（读取持久化状态） */
export function readPuzzleSolved(puzzleId: string): boolean {
  if (typeof window === 'undefined') return false
  return localStorage.getItem(STORAGE_PREFIX + puzzleId) === 'solved'
}

/** 标记已解决（写入持久化状态） */
export function writePuzzleSolved(puzzleId: string): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_PREFIX + puzzleId, 'solved')
}

/** 归一化：去首尾空白 + 小写（与 usePuzzle 一致） */
function normalizeAnswer(value: string): string {
  return value.trim().toLowerCase()
}

/**
 * 校验答案是否正确。
 *
 * @param definition      - 题目定义
 * @param selectedIndices - 选择题已选项下标集合（single/multi 用；fill 传 []）
 * @param fillValues      - 填空输入值列表（fill 用；其余传 []）
 * @returns true 表示答案正确
 */
export function checkPuzzleAnswer(
  definition: PuzzleDefinition,
  selectedIndices: number[],
  fillValues: string[],
): boolean {
  switch (definition.type) {
    case 'single': {
      // 恰选 1 项且该项标记为正确
      if (selectedIndices.length !== 1) return false
      const option = definition.options?.[selectedIndices[0]]
      return option?.correct === true
    }
    case 'multi': {
      // 所选集合与正确集合全等（顺序无关）
      const correctIndices = (definition.options ?? [])
        .map((option, index) => (option.correct ? index : -1))
        .filter((index) => index !== -1)
      const selected = [...selectedIndices].sort((a, b) => a - b)
      const correct = [...correctIndices].sort((a, b) => a - b)
      if (selected.length !== correct.length) return false
      return selected.every((index, i) => index === correct[i])
    }
    case 'fill': {
      const answers = definition.fillAnswers ?? []
      if (fillValues.length !== answers.length) return false
      return fillValues.every((value, i) => normalizeAnswer(value) === normalizeAnswer(answers[i]))
    }
  }
}
