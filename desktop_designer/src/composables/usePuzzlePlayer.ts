/**
 * # usePuzzlePlayer — 题目答案校验（同步副本）
 *
 * 与 desktop/src/composables/usePuzzlePlayer.ts 的校验逻辑同步维护
 * （去掉游戏侧的 solved 持久化，出题器测试场景不需要）。
 *
 * ## 校验规则
 *
 * - `single`：恰选 1 项，且该项 correct
 * - `multi`：所选集合与正确集合全等（顺序无关）
 * - `fill`：每个空 trim 后与 fillAnswers[i] 大小写不敏感比较
 */

import type { PuzzleDefinition } from '@/types/puzzle'

/** 归一化：去首尾空白 + 小写 */
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
      if (selectedIndices.length !== 1) return false
      const option = definition.options?.[selectedIndices[0]]
      return option?.correct === true
    }
    case 'multi': {
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
