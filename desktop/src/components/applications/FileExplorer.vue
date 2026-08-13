<script setup lang="ts">
/**
 * # FileExplorer.vue — 文件资源管理器
 *
 * FakeOS 的文件浏览器，基于统一文件系统（useFileSystem）展示目录和文件。
 * 三面板布局：侧边栏（快速导航） + 主区域（文件列表） + 底部预览区。
 *
 * ## 架构
 *
 * ```
 * FileExplorer.vue
 *  │
 *  ├─ 侧边栏（左侧 130px）
 *  │   ├─ 数据源：useFileSystem.getRootTree() → getVisibleChildren() → 过滤仅 dir
 *  │   ├─ 交互：单击 → 跳转到该目录（从根路径，非拼接）
 *  │   └─ 高亮：当前路径匹配的一级目录高亮
 *  │
 *  ├─ 主区域（flex 填充）
 *  │   ├─ 面包屑：当前路径的逐段显示，可点击回退
 *  │   └─ 文件列表：当前目录下的可见文件和子目录
 *  │       ├─ 目录 → 双击进入子目录
 *  │       ├─ .puz 文件 → 双击打开谜题窗口（查找 puzzleRegistry）
 *  │       └─ 其他文件 → 单击选中预览，双击也选中预览
 *  │
 *  └─ 预览区（底部，最大 120px）
 *      ├─ 显示：选中文件的文件名 + 内容
 *      └─ 隐藏：未选中文件时不显示
 * ```
 *
 * ## 数据流
 *
 * ```
 * useFileSystem.getRootTree()
 *   → getVisibleChildren(tree, player)
 *     → filter(n => n.type === 'dir')     → 侧边栏目录列表
 *     → filter(n => n.type === 'file')    → 文件列表（主区域）
 *
 * useFileSystem.getRootTree()
 *   → 递归查找 currentPath
 *     → getVisibleChildren(subTree, player) → 当前目录内容
 * ```
 *
 * ## 与 useFileSystem 的关系
 *
 * - `getRootTree()` + `getVisibleChildren()` → 驱动所有 UI 数据
 * - `buildPlayerSnapshot()` → 在 setup 阶段调用一次，获取当前玩家权限
 * - 不维护独立的目录列表或文件内容
 *
 * ## 为什么 buildPlayerSnapshot 不在 computed 中
 *
 * 文件系统访问规则在当前会话中固定（用户不会在浏览文件时切换账户）。
 * 在 setup 阶段调用一次即可，无需响应式追踪。
 *
 * ## 双击打开谜题的映射
 *
 * 文件名如 `caesar-cipher.puz`：
 * 1. 去掉 `.puz` 后缀 → `caesar-cipher`
 * 2. 在 `puzzleRegistry` 中查找 key `caesar-cipher`
 * 3. 找到 → 通过 windowService.send() 创建谜题窗口
 */

import { computed, defineAsyncComponent, inject, ref } from 'vue'
import { ChevronRight, File, FileText, Folder } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { unlockAchievementById } from '@/composables/useAchievementUnlocks'
import { playStoryScript } from '@/composables/useStoryDialog'
import { storyScripts } from '@/story'
import { puzzleRegistry } from '@/registries/puzzles'
import {
  getEffectiveContent,
  getRootTree,
  getVisibleChildren,
  buildPlayerSnapshot,
} from '@/composables/useFileSystem'
import type { FileNode } from '@/composables/useFileSystem'
import type { WindowService } from '@/composables/useWindowService'

const { t } = useI18n({ useScope: 'global' })
const windowService = inject<WindowService>('windowService')

/** 文本编辑器（异步加载，双击 .txt/.log 时打开） */
const TextEditor = defineAsyncComponent(() => import('@/components/applications/TextEditor.vue'))

// ─── 状态 ──────────────────────────────────────────

/** 当前导航路径（如 '/', '/home', '/sys/cache'） */
const currentPath = ref('/')

/** 面包屑路径段数组，由 currentPath 派生 */
const pathStack = computed(() => {
  if (currentPath.value === '/') return ['/']
  return ['/', ...currentPath.value.slice(1).split('/')]
})

/** 当前选中的文件节点，驱动底部预览区显示 */
const selectedFile = ref<FileNode | null>(null)

/** 选中文件的有效内容（已合并玩家本地覆盖层，本地版本优先） */
const selectedContent = ref<string | null>(null)

/**
 * 选中文件并刷新底部预览内容。
 *
 * 必须用 getEffectiveContent 合并玩家本地覆盖层：玩家保存后的版本在
 * localStorage（见 usePlayerFiles），不能直接显示静态基线 file.content，
 * 否则预览不会反映玩家修改。每次选中都重新计算，保证读到最新本地版本。
 *
 * @param file - 被单击/双击选中的文件节点
 */
function setSelection(file: FileNode) {
  selectedFile.value = file
  const path = currentPath.value === '/' ? `/${file.name}` : `${currentPath.value}/${file.name}`
  selectedContent.value = getEffectiveContent(path, file.content)
}

// ─── 数据：从统一文件系统获取 ─────────────────────

/** 当前玩家快照（setup 阶段确定，会话内不变） */
const player = buildPlayerSnapshot()

/**
 * 根目录下可见的子目录列表（侧边栏用）。
 * 先从 getRootTree() 获取全量树，再通过 getVisibleChildren 过滤，
 * 最后只保留 type === 'dir' 的节点。
 */
const rootDirs = computed(() => {
  const children = getRootTree() as unknown as FileNode[]
  return getVisibleChildren(children, player).filter((n) => n.type === 'dir')
})

/**
 * 在当前路径下查找目录子节点。
 * 内联实现了 findDir 而非引用 useFileSystem.resolvePath，
 * 因为 resolvePath 内部依赖 useTerminalCwd（终端专有），
 * FileExplorer 有自己的 currentPath 状态，不需要 cwd。
 *
 * @param nodes - 起始目录的子节点
 * @param path  - 目标绝对路径（如 '/', '/home/PLAYER'）
 * @returns 目标目录的子节点列表
 */
function findDir(nodes: readonly FileNode[], path: string): FileNode[] {
  if (path === '/' || path === '') return nodes as FileNode[]
  const segments = path.replace(/^\//, '').split('/')
  let current: readonly FileNode[] = nodes
  for (const seg of segments) {
    const child = current.find((n) => n.name === seg)
    if (!child || child.type !== 'dir') return []
    current = child.children ?? []
  }
  return current as FileNode[]
}

/** 当前路径下的可见内容（目录 + 文件） */
const currentEntries = computed(() => {
  const entries = findDir(getRootTree(), currentPath.value)
  return getVisibleChildren(entries as FileNode[], player)
})

/** 分离目录和文件，分别渲染（目录在前，文件在后） */
const dirs = computed(() => currentEntries.value.filter((n) => n.type === 'dir'))
const files = computed(() => currentEntries.value.filter((n) => n.type === 'file'))

// ─── 操作函数 ──────────────────────────────────────

/**
 * 导航到指定目录。
 * 同时清除文件选中状态，避免预览区显示过期数据。
 *
 * @param path - 绝对路径字符串
 */
function navigateTo(path: string) {
  currentPath.value = path
  selectedFile.value = null
  selectedContent.value = null
}

/**
 * 面包屑点击处理。
 * index=0 → 根目录 '/'；index>0 → 拼接前 index+1 段。
 *
 * @param index - 面包屑段索引（0-based）
 */
function navigateToSegment(index: number) {
  if (index === 0) {
    navigateTo('/')
    return
  }
  const segments = pathStack.value.slice(1, index + 1)
  navigateTo('/' + segments.join('/'))
}

/**
 * 侧边栏目录点击：始终从根路径跳转（不拼接当前路径）。
 * 与主区域中双击目录的行为不同，侧边栏是绝对跳转。
 *
 * @param dirName - 目录名（不含路径前缀）
 */
function handleDirClick(dirName: string) {
  navigateTo('/' + dirName)
}

/**
 * 主区域目录双击：进入**当前路径下**的子目录（拼接 currentPath）。
 *
 * 与侧边栏的区别：
 * - 侧边栏列的是根目录的一级子目录 → 从根绝对跳转（'/' + name）
 * - 主区域列的是当前目录里的子目录 → 必须拼当前路径，
 *   否则从 /home 双击 PLAYER 会错误跳到根下不存在的 /PLAYER（显示空目录）
 *
 * @param dir - 被双击的目录节点
 */
function handleDirDblClick(dir: FileNode) {
  navigateTo(currentPath.value === '/' ? `/${dir.name}` : `${currentPath.value}/${dir.name}`)
}

/**
 * 双击文件处理。
 *
 * 行为：
 * - `.puz` 文件 → 查找 puzzleRegistry，创建谜题窗口
 * - `.txt` / `.log` 文件 → 用文本编辑器打开（独立窗口，文件名命名的 Dock 条目）
 * - 无后缀文件 → 选中并显示预览
 * - 其他文件   → 选中并显示预览
 *
 * @param file - 被双击的文件节点
 */
function handleFileDblClick(file: FileNode) {
  // 通用剧情机制：文件节点绑定成就 id（FileNode.achievementId）时，
  // 首次打开自动解锁，不写死文件名/路径（终端 cat 同样按节点触发）
  unlockAchievementById(file.achievementId)

  // 可执行剧情文件（如 init.exe）：双击即播放绑定脚本
  if (file.storyId) {
    const script = storyScripts[file.storyId]
    if (script) {
      playStoryScript(script)
    }
    return
  }

  const dotIndex = file.name.lastIndexOf('.')
  if (dotIndex <= 0) {
    setSelection(file)
    return
  }

  const ext = file.name.slice(dotIndex)
  if (ext === '.puz') {
    const puzzleId = file.name.slice(0, dotIndex)
    const puzzle = puzzleRegistry.get(puzzleId)
    if (puzzle && windowService) {
      windowService.send({
        type: 'create-window',
        payload: {
          titleKey: puzzle.nameKey,
          title: puzzle.definition?.title,
          icon: File,
          component: puzzle.component,
          componentProps: { puzzleId: puzzle.id },
          defaultWidth: puzzle.defaultWidth,
          defaultHeight: puzzle.defaultHeight,
          placement: 'center',
          resizable: puzzle.resizable ?? true,
        },
      })
    }
    return
  }

  if (ext === '.txt' || ext === '.log') {
    openTextEditor(file)
    return
  }

  setSelection(file)
}

/**
 * 打开文本编辑器窗口。
 *
 * 关键点：
 * - 窗口 ID 由 windowService.createWindow 内部分配，创建成功后回填给编辑器
 *   组件（componentProps.windowId），供其注册关闭会话。
 * - `dockable: true` → DesktopView 按"每个窗口一个条目"渲染到 Dock 栏，
 *   `dockTitle` 取文件名，因此打开多个文件会出现多个命名条目。
 * - 传入绝对路径 `filePath`（编辑器保存时判断是否可写）；
 *   内容用 getEffectiveContent 合并玩家本地覆盖层（本地版本优先）。
 *
 * @param file - 被双击的 .txt / .log 文件节点
 */
function openTextEditor(file: FileNode) {
  if (!windowService) return
  // 由当前导航路径拼出文件绝对路径
  const filePath = currentPath.value === '/' ? `/${file.name}` : `${currentPath.value}/${file.name}`
  const result = windowService.send({
    type: 'create-window',
    payload: {
      titleKey: 'textEditor.title',
      title: file.name,
      icon: FileText,
      component: TextEditor,
      componentProps: {
        fileName: file.name,
        filePath,
        fileContent: getEffectiveContent(filePath, file.content) ?? '',
      },
      defaultWidth: 480,
      defaultHeight: 340,
      placement: 'cascade',
      resizable: true,
      dockable: true,
      dockTitle: file.name,
    },
  })
  if (result) {
    result.componentProps = { ...result.componentProps, windowId: result.id }
  }
}

/**
 * 单击文件：选中并在底部预览区显示简要信息（内容为本地覆盖层优先）。
 *
 * @param file - 被单击的文件节点
 */
function handleFileClick(file: FileNode) {
  setSelection(file)
}
</script>

<template>
  <div class="explorer">
    <!--
      侧边栏：显示根目录下的可见子目录。
      仅显示目录（type === 'dir'），文件不进入侧边栏。
      高亮当前路径匹配的一级目录。
    -->
    <aside class="explorer__sidebar">
      <p class="explorer__sidebar-title">{{ t('applications.files.title') }}</p>
      <ul class="explorer__dir-list">
        <li
          v-for="dir in rootDirs"
          :key="dir.name"
          class="explorer__dir-item"
          :class="{ 'explorer__dir-item--active': currentPath.startsWith('/' + dir.name) && currentPath.split('/')[1] === dir.name }"
          @click="handleDirClick(dir.name)"
        >
          <Folder :size="14" :stroke-width="1.8" />
          <span>{{ dir.name }}/</span>
        </li>
      </ul>
    </aside>

    <!-- 主区域：面包屑导航 + 文件列表 -->
    <div class="explorer__main">
      <!-- 面包屑：当前路径逐段显示，可点击回退到任意上级目录 -->
      <div class="explorer__breadcrumb">
        <template v-for="(seg, i) in pathStack" :key="i">
          <span
            class="explorer__breadcrumb-seg"
            @click="navigateToSegment(i)"
          >{{ seg }}</span>
          <ChevronRight v-if="i < pathStack.length - 1" :size="12" :stroke-width="1.5" class="explorer__breadcrumb-arrow" />
        </template>
      </div>

      <!-- 文件列表：目录在前，文件在后 -->
      <div class="explorer__files">
        <p v-if="currentEntries.length === 0" class="explorer__empty">
          {{ t('applications.files.emptyDir') }}
        </p>

        <!-- 目录：双击进入（拼接当前路径，见 handleDirDblClick） -->
        <div
          v-for="dir in dirs"
          :key="'d-' + dir.name"
          class="explorer__entry"
          @dblclick="handleDirDblClick(dir)"
        >
          <Folder :size="14" :stroke-width="1.8" class="explorer__icon--dir" />
          <span>{{ dir.name }}/</span>
        </div>

        <!-- 文件：单击选中预览，双击操作 -->
        <div
          v-for="file in files"
          :key="'f-' + file.name"
          class="explorer__entry"
          :class="{ 'explorer__entry--selected': selectedFile?.name === file.name }"
          @click="handleFileClick(file)"
          @dblclick="handleFileDblClick(file)"
        >
          <File :size="14" :stroke-width="1.8" class="explorer__icon--file" />
          <span>{{ file.name }}</span>
        </div>
      </div>

      <!-- 底部预览区：选中文件时显示文件名和内容 -->
      <div v-if="selectedFile" class="explorer__preview">
        <div class="explorer__preview-header">
          <span>{{ t('applications.files.previewTitle') }}: {{ selectedFile.name }}</span>
        </div>
        <pre class="explorer__preview-content">{{ selectedContent ?? t('applications.files.cannotOpen') }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.explorer {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* ── 侧边栏 ── */
.explorer__sidebar {
  width: 130px;
  flex-shrink: 0;
  padding: 12px;
  border-right: 1px solid var(--line-subtle);
  background: var(--canvas);
  overflow-y: auto;
}

.explorer__sidebar-title {
  margin: 0 0 8px;
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
  gap: 1px;
}

.explorer__dir-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  color: var(--text-secondary);
  font: 12px var(--font-ui);
  cursor: pointer;
  transition: background-color 0.12s, color 0.12s;
}

.explorer__dir-item:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.explorer__dir-item--active {
  color: var(--signal-mint);
  background: var(--surface-panel);
}

/* ── 主区域 ── */
.explorer__main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.explorer__breadcrumb {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 12px;
  border-bottom: 1px solid var(--line-subtle);
  overflow-x: auto;
  white-space: nowrap;
}

.explorer__breadcrumb-seg {
  color: var(--text-muted);
  font: 11px var(--font-mono);
  cursor: pointer;
  padding: 2px 4px;
  transition: color 0.12s;
}

.explorer__breadcrumb-seg:hover {
  color: var(--text-primary);
}

/* 最后一段不可点击（当前目录） */
.explorer__breadcrumb-seg:last-child {
  color: var(--text-primary);
  cursor: default;
}

.explorer__breadcrumb-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
}

/* ── 文件列表 ── */
.explorer__files {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.explorer__entry {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  color: var(--text-primary);
  font: 13px var(--font-ui);
  cursor: pointer;
  transition: background-color 0.12s;
  user-select: none;
}

.explorer__entry:hover {
  background: var(--surface-hover);
}

.explorer__entry--selected {
  background: var(--surface-panel);
}

.explorer__icon--dir {
  color: var(--signal-mint);
  flex-shrink: 0;
}

.explorer__icon--file {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.explorer__empty {
  margin: 0;
  color: var(--text-muted);
  font: 12px var(--font-ui);
}

/* ── 预览区 ── */
.explorer__preview {
  border-top: 1px solid var(--line-subtle);
  flex-shrink: 0;
  max-height: 120px;
  display: flex;
  flex-direction: column;
}

.explorer__preview-header {
  padding: 4px 12px;
  color: var(--text-muted);
  font: 600 10px var(--font-mono);
  text-transform: uppercase;
  border-bottom: 1px solid var(--line-subtle);
}

.explorer__preview-content {
  margin: 0;
  padding: 8px 12px;
  overflow-y: auto;
  color: var(--text-secondary);
  font: 12px var(--font-mono);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
