/**
 * # useAchievementToasts — 成就解锁弹窗服务
 *
 * 模块级成就通知队列：模拟 Steam 成就解锁——右下角滑入、停留数秒后消失。
 * 多个成就连续解锁时排队逐个显示（与 Steam 行为一致）。
 *
 * ## 为什么是模块级单例
 *
 * - 成就在任意位置解锁（登录、解谜、剧情事件），不限于组件 setup
 * - 队列状态（visible + queue）需要被 AchievementToast.vue 组件响应式渲染，
 *   也需被业务代码调用入队；模块级 ref 让两端共享同一份状态
 * - 与 useFileSystem / useStoryDialog 的模式一致
 *
 * ## 使用示例
 *
 * ```ts
 * import { showAchievementToast } from '@/composables/useAchievementToasts'
 *
 * showAchievementToast({
 *   id: 'first-contact',
 *   nameKey: 'archive.achievementList.firstLogin.name',
 *   descriptionKey: 'archive.achievementList.firstLogin.description',
 * })
 * ```
 */

import { ref } from 'vue'
import type { Component } from 'vue'

/** 成就弹窗条目（渲染时组件内部按 key 翻译） */
export interface AchievementToastItem {
  /** 成就 ID（去重/追踪用） */
  id: string
  /** 成就名称 i18n key */
  nameKey: string
  /** 成就描述 i18n key */
  descriptionKey: string
  /** 自定义图标（缺省用默认奖杯图标） */
  icon?: Component
  /** 自定义图片 URL（如叙事立绘）；提供时优先于 icon 显示 */
  image?: string
}

/** 每条成就的停留时长（ms） */
const DISPLAY_MS = 5000

/** 待显示的成就队列 */
const queue = ref<AchievementToastItem[]>([])
/** 当前正在显示的成就（导出供 AchievementToast.vue 渲染） */
export const visible = ref<AchievementToastItem | null>(null)

let hideTimer: ReturnType<typeof setTimeout> | null = null

/** 清除停留定时器 */
function clearHideTimer() {
  if (hideTimer !== null) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

/** 当前条消失后，从队列取出下一条继续显示 */
function showNext() {
  const next = queue.value.shift()
  if (!next) return
  visible.value = next
  hideTimer = setTimeout(dismiss, DISPLAY_MS)
}

/** 隐藏当前条并触发下一条 */
function dismiss() {
  clearHideTimer()
  visible.value = null
  showNext()
}

/**
 * 弹出成就解锁通知。
 * 已有显示中的成就时自动入队，逐条播放。
 *
 * @param item - 成就信息（i18n key + 可选图标）
 */
export function showAchievementToast(item: AchievementToastItem): void {
  if (visible.value) {
    queue.value.push(item)
    return
  }
  visible.value = item
  hideTimer = setTimeout(dismiss, DISPLAY_MS)
}
