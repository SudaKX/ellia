/**
 * # useAchievementUnlocks — 成就解锁与内置成就定义
 *
 * 统一成就解锁入口：去重（localStorage 记录）→ 弹出成就 toast。
 * 任何"行为达成"处（文件资源管理器点开、终端 cat、解谜等）调用 unlockAchievement 即可，
 * 已解锁的成就不再重复弹。
 *
 * ## 与 useAchievementToasts 的分工
 *
 * - useAchievementToasts：成就通知的显示队列（只管 UI）
 * - useAchievementUnlocks：成就的解锁判定与记录（只管逻辑），复用 toast 队列
 *
 * ## 为什么内置成就定义放在这里
 *
 * 同一成就会被多个触发点共用（如「第一次」= 文件资源管理器点开 + 终端 cat），
 * 集中定义避免各处重复写 nameKey / image，也便于后续按剧情.md 扩展更多成就。
 *
 * ## @example
 *
 * ```ts
 * import { unlockAchievement, FIRST_CONTACT } from '@/composables/useAchievementUnlocks'
 *
 * // 任意触发点：
 * if (unlockAchievement(FIRST_CONTACT)) {
 *   // 首次解锁成功，可执行额外逻辑（如播放对话）
 * }
 * ```
 */

import type { AchievementToastItem } from '@/composables/useAchievementToasts'
import { showAchievementToast } from '@/composables/useAchievementToasts'
import type { AudioService } from '@/composables/useAudioService'

/** 已解锁成就记录 key 前缀（localStorage 持久化，刷新/重复触发不重复弹） */
const UNLOCKED_PREFIX = 'ellia.desktop.achievement.'

/**
 * 音频服务引用（由 DesktopView setup 时注入）。
 * 与剧情对话服务同模式：模块级函数无法 inject，靠 init 注册共享实例。
 */
let audioService: AudioService | null = null

/**
 * 注册 AudioService 实例（DesktopView setup 阶段调用一次）。
 * 成就音效通过同一实例播放，受主音量/静音/频谱控制。
 *
 * @param service - App.vue 提供（provide AudioServiceKey）的音频服务实例
 */
export function initAchievementAudio(service: AudioService): void {
  audioService = service
}

/** 是否已解锁 */
function isUnlocked(id: string): boolean {
  return localStorage.getItem(UNLOCKED_PREFIX + id) !== null
}

/** 标记已解锁 */
function markUnlocked(id: string): void {
  localStorage.setItem(UNLOCKED_PREFIX + id, '1')
}

/**
 * 解锁成就：已解锁直接返回 false；否则播放解锁音效（若配置）并弹出成就 toast。
 *
 * @param item - 成就信息（id 用于去重，其余用于渲染）
 * @returns true 表示本次首次解锁
 */
export function unlockAchievement(item: AchievementToastItem): boolean {
  if (isUnlocked(item.id)) return false
  markUnlocked(item.id)
  // 走音频管线播放解锁语音（音量/静音/频谱统一受 AudioService 控制）
  if (item.sound) {
    audioService?.playFile(item.sound, 'system')
  }
  showAchievementToast(item)
  return true
}

/**
 * 「第一次」成就：首次打开/查看 `/home/看这里看这里.txt` 解锁。
 * 通过文件节点绑定的 achievementId: 'first-contact' 触发（见 useFileSystem），
 * 入口为文件资源管理器双击（FileExplorer）与终端 cat（commands/cat.ts）。
 */
export const FIRST_CONTACT: AchievementToastItem = {
  id: 'first-contact',
  nameKey: 'archive.achievementList.firstContact.name',
  descriptionKey: 'archive.achievementList.firstContact.description',
  image: `${import.meta.env.BASE_URL}images/kei/kei_happy2.webp`,
  // 解锁语音：kei 的"老师请求的话……也没办法了呢"（走音频管线播放）
  sound: `${import.meta.env.BASE_URL}sounds/kei/kei_老师请求的话……也没办法了呢.ogg`,
}

/** 内置成就注册表：id → 定义（FileNode.achievementId 引用此 id） */
const ACHIEVEMENT_BY_ID: Record<string, AchievementToastItem> = {
  'first-contact': FIRST_CONTACT,
}

/**
 * 按成就 id 解锁（通用剧情入口）。
 * 调用方只需从文件节点/事件处拿到 id，无需感知具体成就内容。
 *
 * @param id - 成就 id（FileNode.achievementId）；未绑定/未知 id 时静默返回 false
 * @returns true 表示本次首次解锁
 */
export function unlockAchievementById(id?: string): boolean {
  if (!id) return false
  const item = ACHIEVEMENT_BY_ID[id]
  if (!item) return false
  return unlockAchievement(item)
}
