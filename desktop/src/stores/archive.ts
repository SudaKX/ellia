/**
 * # 玩家档案 Store (archiveStore)
 *
 * 管理玩家档案数据的获取与缓存。
 *
 * ## 架构
 *
 * ```
 * ArchiveViewer.vue               ← 消费层
 *   └─ archiveStore.fetch()       ← Pinia store
 *        ├─ 生产环境：fetch('/api/player/archive')   ← 真实 API
 *        └─ 开发/演示：getMockArchive()                ← mock 数据
 * ```
 *
 * ## API 边界设计
 *
 * `fetchPlayerArchive()` 是唯一的数据入口。
 * 后端就绪后，只需替换此函数内部实现，消费层（ArchiveViewer.vue）无需任何改动。
 *
 * ## 为什么 playerArchive 用单个对象而非数组
 *
 * 每个玩家只有一个档案，不存在列表场景。
 * 单个 ref 比 Map/List 更直观。
 *
 * ## i18n 与类型分离
 *
 * 成就的 `nameKey`/`descriptionKey` 存储在数据中（i18n key），
 * 渲染时由 View 层调用 `t()` 翻译。这是与命令系统一致的模式。
 */

import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { PlayerArchive, Achievement, PuzzleCompletion } from '@/types/desktop'

/**
 * 生成 mock 玩家档案数据。
 * 模拟从后端拉取的 JSON 结构，字段命名与 `PlayerArchive` 接口一致。
 */
function getMockArchive(): PlayerArchive {
  return {
    userId: 'PLAYER',
    privilegeClass: 'LIMITED',
    createdAt: '2026-06-15T08:30:00.000Z',
    lastLoginAt: '2026-07-21T14:22:10.000Z',
    loginCount: 17,
    puzzleCompletions: [
      {
        puzzleId: 'caesar-cipher',
        completedAt: '2026-07-18T10:15:00.000Z',
        attempts: 2,
        hintsUsed: 0,
      },
      {
        puzzleId: 'binary-grid',
        completedAt: '2026-07-20T16:45:00.000Z',
        attempts: 5,
        hintsUsed: 1,
      },
    ],
    achievements: [
      {
        id: 'first-login',
        nameKey: 'archive.achievementList.firstLogin.name',
        descriptionKey: 'archive.achievementList.firstLogin.description',
        unlockedAt: '2026-06-15T08:30:00.000Z',
      },
      {
        id: 'first-puzzle',
        nameKey: 'archive.achievementList.firstPuzzle.name',
        descriptionKey: 'archive.achievementList.firstPuzzle.description',
        unlockedAt: '2026-07-18T10:15:00.000Z',
      },
      {
        id: 'three-logins',
        nameKey: 'archive.achievementList.threeLogins.name',
        descriptionKey: 'archive.achievementList.threeLogins.description',
        unlockedAt: '2026-07-01T09:00:00.000Z',
      },
      {
        id: 'persistent',
        nameKey: 'archive.achievementList.persistent.name',
        descriptionKey: 'archive.achievementList.persistent.description',
        unlockedAt: null,
      },
    ],
    totalPlaytimeSeconds: 4200,
  }
}

export const useArchiveStore = defineStore('archive', () => {
  /** 玩家档案原始数据 */
  const playerArchive = ref<PlayerArchive | null>(null)

  /** 数据是否正在加载 */
  const isLoading = ref(false)

  /** 加载是否出错 */
  const error = ref<string | null>(null)

  /** 已解锁的成就 */
  const unlockedAchievements = computed(() =>
    playerArchive.value?.achievements.filter((a) => a.unlockedAt !== null) ?? [],
  )

  /** 已完成的谜题数量 */
  const completedPuzzleCount = computed(() =>
    playerArchive.value?.puzzleCompletions.length ?? 0,
  )

  /**
   * 从数据源获取玩家档案。
   *
   * 当前使用 mock 数据。后端就绪后，替换为：
   * ```ts
   * const response = await fetch('/api/player/archive')
   * const data = await response.json()
   * playerArchive.value = data
   * ```
   */
  async function fetchPlayerArchive(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      // TODO: 替换为真实 API 调用
      // const response = await fetch('/api/player/archive')
      // if (!response.ok) throw new Error(`HTTP ${response.status}`)
      // playerArchive.value = await response.json()

      // 模拟网络延迟（300-600ms），让 loading 状态可见
      await new Promise((r) => setTimeout(r, 300 + Math.random() * 300))

      playerArchive.value = getMockArchive()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('[archiveStore] Failed to fetch player archive:', err)
    } finally {
      isLoading.value = false
    }
  }

  return {
    playerArchive,
    isLoading,
    error,
    unlockedAchievements,
    completedPuzzleCount,
    fetchPlayerArchive,
  }
})
