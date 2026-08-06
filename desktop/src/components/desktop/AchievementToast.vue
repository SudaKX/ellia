<script setup lang="ts">
/**
 * # AchievementToast.vue — 成就解锁弹窗
 *
 * 模仿 Steam 成就解锁通知：从右下角滑入，停留数秒后自动滑出。
 * 由 useAchievementToasts 服务驱动（模块级队列），本组件只负责渲染。
 *
 * ## 视觉设计（Steam × FakeOS）
 *
 * - **Steam 特征**：暗色卡片 + 左侧图标块 + 右侧"标题小字/成就名/描述"三段式
 * - **FakeOS 化**：`border-radius: 0`、mono 字体、信号薄荷色图标、面板变量
 * - 右上角小字显示解锁时间（当前时间），增强真实感
 *
 * ## 层级与位置
 *
 * - `z-index: 1150`：高于模态遮罩（1100）与 Dock（100），低于模态窗口（1200），
 *   保证不遮挡正在进行的模态交互，又不被 Dock 覆盖
 * - `bottom: 84px`：避开 Dock 栏（~46px 高度 + 间距）
 *
 * ## 为什么是队列而非多个同时显示
 *
 * Steam 成就也是排队逐个弹出。模块级队列（useAchievementToasts）
 * 保证连续解锁时逐条播放，避免多个 toast 互相遮挡。
 *
 * ## @example
 *
 * ```vue
 * <!-- DesktopView 中挂载一次即可 -->
 * <AchievementToast />
 * ```
 */

import { computed } from 'vue'
import { Trophy } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

import { visible } from '@/composables/useAchievementToasts'

const { t } = useI18n({ useScope: 'global' })

/** 当前成就的显示图标（缺省奖杯） */
const iconComponent = computed(() => visible.value?.icon ?? Trophy)

/** 解锁时间（当前时刻，格式随系统语言） */
const unlockedTime = computed(() =>
  new Intl.DateTimeFormat(navigator.language, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date()),
)
</script>

<template>
  <Transition name="achievement-toast">
    <div
      v-if="visible"
      class="achievement-toast"
      role="status"
      aria-live="polite"
    >
      <div class="achievement-toast__icon" aria-hidden="true">
        <component :is="iconComponent" :size="22" :stroke-width="1.7" />
      </div>
      <div class="achievement-toast__body">
        <p class="achievement-toast__title">
          {{ t('achievements.toastTitle') }}
          <span class="achievement-toast__time">{{ unlockedTime }}</span>
        </p>
        <p class="achievement-toast__name">{{ t(visible.nameKey) }}</p>
        <p class="achievement-toast__desc">{{ t(visible.descriptionKey) }}</p>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.achievement-toast {
  position: fixed;
  right: 16px;
  bottom: 84px;
  z-index: 1150;
  display: flex;
  align-items: stretch;
  width: 320px;
  max-width: calc(100vw - 32px);
  border: 1px solid var(--line-default);
  border-radius: 0;
  background: var(--surface-raised);
  box-shadow: 0 14px 44px rgb(0 0 0 / 45%), 0 0 0 1px rgb(255 255 255 / 3%) inset;
  overflow: hidden;
}

/* Steam 式左侧图标块 */
.achievement-toast__icon {
  display: grid;
  flex-shrink: 0;
  width: 56px;
  place-items: center;
  border-right: 1px solid var(--line-subtle);
  background: var(--surface-panel);
  color: var(--signal-mint);
}

.achievement-toast__body {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
  padding: 10px 14px;
}

/* Steam 式小字标题（大写 mono） */
.achievement-toast__title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin: 0;
  color: var(--signal-mint);
  font: 700 10px var(--font-mono);
  letter-spacing: 0.1em;
}

.achievement-toast__time {
  color: var(--text-muted);
  font-size: 9px;
  letter-spacing: 0.03em;
}

.achievement-toast__name {
  margin: 0;
  color: var(--text-primary);
  font: 700 14px var(--font-ui);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.achievement-toast__desc {
  margin: 0;
  color: var(--text-secondary);
  font: 11px/1.45 var(--font-ui);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── 滑入 / 滑出动画（Steam 式右滑） ── */
.achievement-toast-enter-active,
.achievement-toast-leave-active {
  transition: transform 0.28s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.22s ease;
}

.achievement-toast-enter-from,
.achievement-toast-leave-to {
  transform: translateX(120%);
  opacity: 0;
}
</style>
