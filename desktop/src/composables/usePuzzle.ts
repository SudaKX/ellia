/**
 * # usePuzzle — 谜题组件运行时 API
 *
 * 谜题组件通过此 composable 访问谜题状态、提交答案、请求提示。
 *
 * ## 状态机
 *
 * ```
 * unsolved ──submitAnswer(true)──→ solved
 * ```
 *
 * ## 使用示例
 *
 * ```ts
 * // 在谜题组件中
 * const { state, submitAnswer, requestHint, hints } = usePuzzle('caesar-cipher')
 *
 * function check() {
 *   if (submitAnswer(userInput.value)) {
 *     // 显示成功动画
 *   }
 * }
 * ```
 *
 * ## 状态持久化
 *
 * `solved` 状态存储在 localStorage 中，key 为 `ellia.puzzle.{id}`。
 * 刷新页面后已解谜的状态会保留，谜题组件可以据此显示不同的 UI。
 *
 * ## 为什么用 composable 而不是 Pinia store
 *
 * - 谜题状态是局部的（每个谜题组件独立），不需要全局共享
 * - 每个谜题的逻辑是自包含的，Pinia store 会引入不必要的复杂度
 * - composable 的响应式 ref 天然适合 Vue 组件使用
 */

import { computed, ref } from 'vue'

export type PuzzleState = 'unsolved' | 'solved'

/** localStorage key 前缀 */
const STORAGE_PREFIX = 'ellia.puzzle.'

/**
 * 谜题组件运行时 Hook。
 *
 * @param puzzleId - 谜题唯一标识（与 registerPuzzle 中的 id 对应）
 * @param correctAnswer - 正确答案（用于比较，也可传自定义验证函数）
 * @returns 谜题状态 + 操作方法
 */
export function usePuzzle(puzzleId: string, correctAnswer?: string) {
  // ── 从 localStorage 读取已解状态 ──
  const storageKey = `${STORAGE_PREFIX}${puzzleId}`
  const initialSolved = typeof window !== 'undefined' && localStorage.getItem(storageKey) === 'solved'

  /** 谜题当前状态 */
  const state = ref<PuzzleState>(initialSolved ? 'solved' : 'unsolved')

  /** 已揭示的提示索引列表 */
  const revealedHintIndices = ref<number[]>([])

  /** 已揭示的提示数量 */
  const hintCount = computed(() => revealedHintIndices.value.length)

  /**
   * 提交答案。
   *
   * @param answer - 用户输入的答案
   * @returns true 表示答案正确，谜题标记为已解决
   */
  function submitAnswer(answer: string): boolean {
    if (state.value === 'solved') return true

    // 大小写不敏感比较，去除首尾空白
    const normalized = answer.trim().toLowerCase()

    if (correctAnswer && normalized === correctAnswer.toLowerCase()) {
      state.value = 'solved'
      // 持久化已解状态
      if (typeof window !== 'undefined') {
        localStorage.setItem(storageKey, 'solved')
      }
      return true
    }

    return false
  }

  /**
   * 请求查看提示。
   * 每次调用揭示下一个提示，已全部揭示后返回 null。
   *
   * @param hints - 提示列表（谜题组件传入）
   * @returns 本次揭示的提示文本，或 null（无更多提示）
   */
  function requestHint(hints: string[]): string | null {
    const nextIndex = revealedHintIndices.value.length
    if (nextIndex >= hints.length) return null

    revealedHintIndices.value.push(nextIndex)
    return hints[nextIndex]
  }

  /**
   * 重置谜题状态（仅开发调试用）。
   * 清除 localStorage 中的已解记录。
   */
  function reset() {
    state.value = 'unsolved'
    revealedHintIndices.value = []
    if (typeof window !== 'undefined') {
      localStorage.removeItem(storageKey)
    }
  }

  return {
    state,
    hintCount,
    submitAnswer,
    requestHint,
    reset,
  }
}
