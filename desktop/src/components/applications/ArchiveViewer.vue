<script setup lang="ts">
/**
 * # ArchiveViewer.vue — 玩家档案查看器
 *
 * 从后端拉取玩家数据（JSON），以自然语言形式展示。
 *
 * ## 架构
 *
 * ```
 * ArchiveViewer.vue
 *  ├─ onMounted → archiveStore.fetchPlayerArchive()
 *  ├─ 加载态 → 骨架屏
 *  ├─ 错误态 → 错误信息 + 重试按钮
 *  └─ 数据态 → 自然语言展示
 *       ├─ 档案信息（用户 ID、权限、注册时间、登录次数、游玩时间）
 *       ├─ 统计数据（已完成谜题列表，自然语言叙述）
 *       └─ 成就列表（已解锁 / 未解锁，含解锁时间）
 * ```
 *
 * ## "自然语言展示"的含义
 *
 * 后端返回的 JSON 是结构化数据（如 `{ puzzlesCompleted: 3 }`），
 * 本组件将其转换为可读的自然语言句子：
 * - "你已完成 3 个谜题。"
 * - "· 'caesar-cipher' — 2 次尝试后解出，使用了 0 个提示。"
 *
 * 所有文案通过 i18n 管理，语言跟随系统设置自动切换。
 *
 * ## 为什么用 Pinia store 而非直接在组件内 fetch
 *
 * - 档案数据可能在多个地方使用（后续的 Sandbox 控制面板等）
 * - store 提供统一的缓存和加载状态管理
 * - mock 数据与真实 API 的切换只需修改 store，组件无需改动
 *
 * ## API 边界
 *
 * 后端就绪后，在 `stores/archive.ts` 的 `fetchPlayerArchive()` 中
 * 将 mock 数据替换为 `fetch('/api/player/archive')` 即可。
 * 组件代码无需任何修改。
 */

import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useArchiveStore } from '@/stores/archive'

const { t } = useI18n({ useScope: 'global' })
const archive = useArchiveStore()

onMounted(() => {
  // 仅在数据未加载时触发 fetch（避免每次打开窗口都重新请求）
  if (!archive.playerArchive && !archive.isLoading) {
    archive.fetchPlayerArchive()
  }
})

/**
 * 格式化 ISO 日期为可读字符串。
 * 根据当前 locale 显示不同格式。
 */
function formatDate(iso: string): string {
  const date = new Date(iso)
  return new Intl.DateTimeFormat(navigator.language, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

/**
 * 格式化游玩时间为可读字符串。
 * 小于 1 小时显示分钟，大于等于 1 小时显示 "Xh Ym"。
 */
function formatPlaytime(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) {
    return t('archive.playtimeMinutes', { minutes: String(minutes) })
  }
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return t('archive.playtimeHours', { hours: String(hours), minutes: String(remainingMinutes) })
}
</script>

<template>
  <div class="archive">
    <!-- 加载态 -->
    <div v-if="archive.isLoading" class="archive__loading">
      <p class="archive__loading-text">{{ t('archive.loading') }}</p>
    </div>

    <!-- 错误态 -->
    <div v-else-if="archive.error" class="archive__error">
      <p class="archive__error-text">{{ t('archive.error') }}</p>
      <p class="archive__error-detail">{{ archive.error }}</p>
      <button class="archive__retry-btn" @click="archive.fetchPlayerArchive()">
        {{ t('archive.retry') }}
      </button>
    </div>

    <!-- 数据态 -->
    <template v-else-if="archive.playerArchive">
      <header class="archive__header">
        <p class="archive__label">{{ t('archive.label') }}</p>
      </header>

      <div class="archive__body">
        <!-- ── 档案信息 ── -->
        <section class="archive__section">
          <h3 class="archive__section-title">{{ t('archive.profile') }}</h3>
          <dl class="archive__dl">
            <div class="archive__dl-row">
              <dt>{{ t('archive.userId') }}</dt>
              <dd>{{ archive.playerArchive.userId }}</dd>
            </div>
            <div class="archive__dl-row">
              <dt>{{ t('archive.privilege') }}</dt>
              <dd class="archive__privilege">{{ archive.playerArchive.privilegeClass }}</dd>
            </div>
            <div class="archive__dl-row">
              <dt>{{ t('archive.registered') }}</dt>
              <dd>{{ formatDate(archive.playerArchive.createdAt) }}</dd>
            </div>
            <div class="archive__dl-row">
              <dt>{{ t('archive.lastLogin') }}</dt>
              <dd>{{ formatDate(archive.playerArchive.lastLoginAt) }}</dd>
            </div>
            <div class="archive__dl-row">
              <dt>{{ t('archive.loginCount') }}</dt>
              <dd>{{ archive.playerArchive.loginCount }}</dd>
            </div>
            <div class="archive__dl-row">
              <dt>{{ t('archive.playtime') }}</dt>
              <dd>{{ formatPlaytime(archive.playerArchive.totalPlaytimeSeconds) }}</dd>
            </div>
          </dl>
        </section>

        <!-- ── 统计数据（自然语言） ── -->
        <section class="archive__section">
          <h3 class="archive__section-title">{{ t('archive.stats') }}</h3>

          <!-- 谜题完成统计 -->
          <p class="archive__narrative">
            {{ t('archive.puzzlesCompletedText', { count: String(archive.completedPuzzleCount) }) }}
          </p>

          <ul v-if="archive.playerArchive.puzzleCompletions.length > 0" class="archive__puzzle-list">
            <li
              v-for="p in archive.playerArchive.puzzleCompletions"
              :key="p.puzzleId"
              class="archive__puzzle-item"
            >
              {{ t('archive.puzzleRecord', { id: p.puzzleId, attempts: String(p.attempts), hints: String(p.hintsUsed) }) }}
            </li>
          </ul>
          <p v-else class="archive__empty">
            {{ t('archive.noPuzzles') }}
          </p>
        </section>

        <!-- ── 成就列表 ── -->
        <section class="archive__section">
          <h3 class="archive__section-title">
            {{ t('archive.achievements') }}
            <span class="archive__section-badge">
              {{ t('archive.achievementsUnlocked', { unlocked: String(archive.unlockedAchievements.length), total: String(archive.playerArchive.achievements.length) }) }}
            </span>
          </h3>

          <ul class="archive__achievement-list">
            <li
              v-for="a in archive.playerArchive.achievements"
              :key="a.id"
              class="archive__achievement-item"
              :class="{ 'archive__achievement-item--locked': !a.unlockedAt }"
            >
              <span class="archive__achievement-icon">
                {{ a.unlockedAt ? '✓' : '✗' }}
              </span>
              <div class="archive__achievement-text">
                <strong>{{ t(a.nameKey) }}</strong>
                <span>{{ t(a.descriptionKey) }}</span>
              </div>
              <span class="archive__achievement-date">
                {{ a.unlockedAt ? t('archive.unlockedAt', { date: formatDate(a.unlockedAt) }) : '' }}
              </span>
            </li>
          </ul>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.archive {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* ── 加载态 ── */
.archive__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.archive__loading-text {
  color: var(--text-muted);
  font: 13px var(--font-mono);
}

/* ── 错误态 ── */
.archive__error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 8px;
  padding: 20px;
  text-align: center;
}

.archive__error-text {
  margin: 0;
  color: var(--signal-red);
  font: 600 13px var(--font-ui);
}

.archive__error-detail {
  margin: 0;
  color: var(--text-muted);
  font: 11px var(--font-mono);
}

.archive__retry-btn {
  margin-top: 4px;
  padding: 4px 16px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: var(--surface-panel);
  font: 12px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s;
}

.archive__retry-btn:hover {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}

/* ── 主区域 ── */
.archive__header {
  padding: 14px 18px 0;
}

.archive__label {
  margin: 0;
  color: var(--signal-red-soft);
  font: 700 10px var(--font-mono);
  text-transform: uppercase;
}

.archive__body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ── 分区 ── */
.archive__section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.archive__section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: var(--text-primary);
  font: 600 12px var(--font-ui);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.archive__section-badge {
  color: var(--text-muted);
  font: 11px var(--font-mono);
  text-transform: none;
  letter-spacing: 0;
}

/* ── 键值对列表 ── */
.archive__dl {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid var(--line-subtle);
}

.archive__dl-row {
  display: flex;
  border-bottom: 1px solid var(--line-subtle);
}

.archive__dl-row:last-child {
  border-bottom: none;
}

.archive__dl-row dt {
  width: 130px;
  flex-shrink: 0;
  padding: 6px 10px;
  color: var(--text-muted);
  font: 11px var(--font-mono);
  background: var(--canvas);
}

.archive__dl-row dd {
  flex: 1;
  margin: 0;
  padding: 6px 10px;
  color: var(--text-primary);
  font: 12px var(--font-mono);
  background: var(--surface-panel);
}

.archive__privilege {
  color: var(--signal-red-soft) !important;
}

/* ── 自然语言叙述 ── */
.archive__narrative {
  margin: 0;
  color: var(--text-secondary);
  font: 13px/1.6 var(--font-ui);
}

.archive__puzzle-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.archive__puzzle-item {
  margin: 0;
  color: var(--text-secondary);
  font: 12px var(--font-mono);
}

.archive__empty {
  margin: 0;
  color: var(--text-muted);
  font: 12px var(--font-ui);
  font-style: italic;
}

/* ── 成就列表 ── */
.archive__achievement-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid var(--line-subtle);
}

.archive__achievement-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--line-subtle);
  background: var(--surface-panel);
}

.archive__achievement-item:last-child {
  border-bottom: none;
}

.archive__achievement-item--locked {
  background: var(--canvas);
  opacity: 0.5;
}

.archive__achievement-icon {
  flex-shrink: 0;
  width: 18px;
  text-align: center;
  font: 12px var(--font-mono);
  color: var(--signal-mint);
}

.archive__achievement-item--locked .archive__achievement-icon {
  color: var(--text-muted);
}

.archive__achievement-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.archive__achievement-text strong {
  color: var(--text-primary);
  font: 600 12px var(--font-ui);
}

.archive__achievement-text span {
  color: var(--text-muted);
  font: 11px var(--font-ui);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.archive__achievement-date {
  flex-shrink: 0;
  color: var(--text-muted);
  font: 10px var(--font-mono);
  white-space: nowrap;
}
</style>
