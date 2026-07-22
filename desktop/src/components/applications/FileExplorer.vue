<script setup lang="ts">
/**
 * # FileExplorer.vue — 文件资源管理器
 *
 * FakeOS 的文件浏览器，展示系统目录和谜题文件。
 * 双击 `.puz` 文件可打开对应谜题窗口。
 *
 * ## 架构
 *
 * ```
 * FileExplorer.vue
 *  ├─ 侧边目录树（静态：系统目录列表）
 *  └─ 文件列表
 *       ├─ 从 puzzleRegistry 读取已注册谜题，显示为 .puz 文件
 *       └─ @dblclick → inject('windowService') → send('create-window')
 * ```
 *
 * ## 为什么用 provide/inject 获取 windowService
 *
 * 与 Terminal.vue 同理——`useWindowService()` 每次调用创建新实例，
 * 必须使用 DesktopView 持有的单例才能向桌面添加窗口。
 *
 * ## 双击打开谜题
 *
 * 文件列表中 `.puz` 后缀的文件双击时：
 * 1. 从 `puzzleRegistry` 查找对应 puzzleId
 * 2. 通过 `windowService.send()` 创建谜题窗口
 * 3. 窗口居中显示，使用谜题注册时的尺寸
 */

import { inject } from 'vue'
import { Puzzle, Folder, File } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { puzzleRegistry } from '@/registries/puzzles'
import type { WindowService } from '@/composables/useWindowService'

const { t } = useI18n({ useScope: 'global' })

/** 从 DesktopView 注入的 windowService 单例 */
const windowService = inject<WindowService>('windowService')

/** 系统目录列表（静态，与 ls 命令的 mock 文件树一致） */
const directories = [
  { name: 'bin', icon: Folder },
  { name: 'etc', icon: Folder },
  { name: 'home', icon: Folder },
  { name: 'puzzles', icon: Puzzle },
  { name: 'sys', icon: Folder },
  { name: 'tmp', icon: Folder },
]

/** 当前选中的目录 */
const selectedDir = 'puzzles'

/**
 * 双击文件时的处理逻辑。
 * `.puz` 文件 → 查找 puzzleRegistry → 创建谜题窗口。
 */
function handleFileDblClick(puzzleId: string) {
  const puzzle = puzzleRegistry.get(puzzleId)
  if (!puzzle || !windowService) return

  windowService.send({
    type: 'create-window',
    payload: {
      titleKey: puzzle.nameKey,
      icon: Puzzle,
      component: puzzle.component,
      componentProps: { puzzleId: puzzle.id },
      defaultWidth: puzzle.defaultWidth,
      defaultHeight: puzzle.defaultHeight,
      placement: 'center',
      resizable: puzzle.resizable ?? true,
    },
  })
}
</script>

<template>
  <div class="explorer">
    <!-- 侧边栏：目录树 -->
    <aside class="explorer__sidebar">
      <p class="explorer__sidebar-title">{{ t('applications.files.title') }}</p>
      <ul class="explorer__dir-list">
        <li
          v-for="dir in directories"
          :key="dir.name"
          class="explorer__dir-item"
          :class="{ 'explorer__dir-item--active': dir.name === selectedDir }"
        >
          <component :is="dir.icon" :size="14" :stroke-width="1.8" />
          <span>{{ dir.name }}/</span>
        </li>
      </ul>
    </aside>

    <!-- 主区域：文件列表 -->
    <div class="explorer__main">
      <div class="explorer__toolbar">
        <span class="explorer__path">/{{ selectedDir }}/</span>
      </div>

      <div class="explorer__files">
        <!-- 谜题文件列表（来自 puzzleRegistry） -->
        <p
          v-for="[id, puzzle] in puzzleRegistry"
          :key="id"
          class="explorer__file"
          @dblclick="handleFileDblClick(id)"
        >
          <File :size="14" :stroke-width="1.8" />
          <span>{{ id }}.puz</span>
        </p>

        <!-- 无谜题时的占位 -->
        <p v-if="puzzleRegistry.size === 0" class="explorer__empty">
          {{ t('puzzles.noPuzzles') }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.explorer {
  display: flex;
  height: 100%;
}

/* ── 侧边栏 ── */
.explorer__sidebar {
  width: 150px;
  flex-shrink: 0;
  padding: 14px;
  border-right: 1px solid var(--line-subtle);
  background: var(--canvas);
}

.explorer__sidebar-title {
  margin: 0 0 10px;
  color: var(--text-muted);
  font: 600 10px var(--font-mono);
  text-transform: uppercase;
}

.explorer__dir-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.explorer__dir-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  color: var(--text-secondary);
  font: 12px var(--font-ui);
  cursor: default;
  transition: background-color 0.12s;
}

.explorer__dir-item:hover {
  background: var(--surface-hover);
}

.explorer__dir-item--active {
  color: var(--signal-red-soft);
  background: var(--surface-panel);
}

/* ── 主区域 ── */
.explorer__main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.explorer__toolbar {
  display: flex;
  align-items: center;
  padding: 8px 14px;
  border-bottom: 1px solid var(--line-subtle);
}

.explorer__path {
  color: var(--text-muted);
  font: 12px var(--font-mono);
}

/* ── 文件列表 ── */
.explorer__files {
  flex: 1;
  overflow-y: auto;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.explorer__file {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 6px 8px;
  color: var(--text-primary);
  font: 13px var(--font-ui);
  cursor: pointer;
  transition: background-color 0.12s;
  user-select: none;
}

.explorer__file:hover {
  background: var(--surface-hover);
}

.explorer__empty {
  margin: 0;
  color: var(--text-muted);
  font: 12px var(--font-ui);
}
</style>
