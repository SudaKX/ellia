<script setup lang="ts">
/**
 * # DesktopView — FakeOS 桌面主视图
 *
 * 本组件是 FakeOS 的根视图，负责组织所有桌面子组件并协调它们之间的交互。
 *
 * ## 组件树
 *
 * ```
 * DesktopView
 *  ├─ DesktopStatusBar        顶部状态栏（用户标识 + 时钟 + 系统菜单）
 *  │    ├─ NetworkMenu         网络状态菜单 → emit('action') → 创建模态弹窗
 *  │    ├─ SoundMenu           音量控制菜单 → Pinia audioStore
 *  │    └─ PowerMenu           电源控制菜单 → 切换账户 / 重启 / 关机
 *  │
 *  ├─ desktop-workspace        工作区（网格背景 + 窗口层）
 *  │    └─ WindowFrame[]        窗口实例列表（由 windowService 驱动）
 *  │
 *  ├─ desktop-modal-overlay    模态遮罩（有 modal 窗口时显示）
 *  │
 *  ├─ Launchpad                应用启动器（快捷键 / Dock 唤起）
 *  │
 *  └─ DockBar                  底部停靠栏（已打开应用 + 全局入口）
 * ```
 *
 * ## 事件流
 *
 * ```
 * NetworkMenu → emit('action', 'disconnect')
 *   → DesktopStatusBar → emit('networkAction', 'disconnect')
 *     → DesktopView.handleNetworkAction()
 *       → windowService.send({ type: 'create-window', mode: 'modal' })
 *         → MessageBox + PermissionDenied（模态弹窗）
 *
 * DockBar → emit('click', appId)
 *   → DesktopView.handleDockAppClick()
 *     → windowService.open(appId) 或 focus() 或 minimize()
 * ```
 *
 * ## 滤镜系统
 *
 * 每个应用窗口共享一个 `windowGlitchFilter` 实例（SVG 滤镜）。
 * `windowFilterIds` 映射 FilterType → filterId，通过 props 传递给 WindowFrame。
 * 窗口根据自身的 `filters` 配置决定是否启用对应滤镜。
 */

import { computed, markRaw, onBeforeUnmount, onMounted, provide, reactive, ref, watch } from 'vue'
import { Bot, Info } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { AiAttachIcon, AiDetachIcon } from '@/ai/icons'
import { getAiLiaisonState, requestAiAttach, requestAiDetach, requestAiDragEnd, requestAiDragMove } from '@/ai/useAiLiaison'
import { useAuth } from '@/composables/useAuth'

import DesktopStatusBar from '@/components/desktop/DesktopStatusBar.vue'
import DockBar from '@/components/desktop/DockBar.vue'
import type { DockApplicationState, DockClickTarget } from '@/components/desktop/DockBar.vue'
import AchievementToast from '@/components/desktop/AchievementToast.vue'
import Launchpad from '@/components/desktop/Launchpad.vue'
import MatrixRain from '@/components/desktop/MatrixRain.vue'
import MessageBox from '@/components/desktop/MessageBox.vue'
import PermissionDenied from '@/components/desktop/PermissionDenied.vue'
import WindowFrame from '@/components/desktop/WindowFrame.vue'
import AiAssistant from '@/components/applications/AiAssistant.vue'
// Live2D 已归档至 desktop/archive/live2d — 恢复时先移回组件与资源，再取消下方注释 + initLive2dWindow()
// import Live2DAssistant from '@/components/applications/Live2DAssistant.vue'
import { initAchievementAudio } from '@/composables/useAchievementUnlocks'
import { useAudioService, type AudioCue } from '@/composables/useAudioService'
import { useFilterService } from '@/composables/useFilterService'
import type { GlitchOptions } from '@/composables/useGlitchFilter'
import { requestTextEditorClose } from '@/composables/useTextEditorSession'
import { initStoryDialog } from '@/composables/useStoryDialog'
import { loadPublishedPuzzles } from '@/composables/usePuzzleLibrary'
import { useWindowService } from '@/composables/useWindowService'
import { applicationRegistry } from '@/registries/applications'
import type { FilterType } from '@/registries/filters'
import { useDesktopStore } from '@/stores/desktop'
import { useCreditsStore } from '@/stores/credits'
import type { ApplicationId } from '@/types/desktop'

// 副作用导入：注册所有谜题（谜题组件通过 defineAsyncComponent 异步加载）
import '@/registries/puzzle-list'

const desktop = useDesktopStore()
const creditsStore = useCreditsStore()
const windowService = useWindowService()
// 提供给子组件（Terminal.vue 通过 inject 获取，用于 sil 命令打开谜题窗口）
provide('windowService', windowService)
// 注册剧情对话服务（openStoryDialog 从任意位置调用）
initStoryDialog(windowService)
const audioService = useAudioService()
// 注册成就音效服务（unlockAchievement 播放解锁语音）
initAchievementAudio(audioService)
// 拉取出题器发布的已审核题目（fire-and-forget，开关 USE_PUBLISHED_QUESTIONS 控制）
void loadPublishedPuzzles()
const filterService = useFilterService()
const { t } = useI18n({ useScope: 'global' })
const router = useRouter()
const auth = useAuth()

/** 窗口 Glitch 滤镜的默认参数 */
const windowGlitchOptions: GlitchOptions = {
  intensity: 12,
  frequencyX: 0.002,
  frequencyY: 0.05,
  enableHorizontalDisplacement: true,
  enableVerticalDisplacement: false,
  chromaticAberration: 0.002,
  animate: true,
  frameSkip: 8,
}
const windowGlitchFilter = filterService.create('glitch', windowGlitchOptions)

/** 滤镜 ID 映射，供 WindowFrame 读取对应滤镜的 SVG filter id */
const windowFilterIds: Partial<Record<FilterType, string>> = {
  glitch: windowGlitchFilter.filterId,
}

/** 网络菜单的动作类型 */
type NetworkAction = 'disconnect' | 'edit-ip' | 'edit-dns'

/** 每个网络动作对应的模态弹窗标题（i18n key） */
const networkMessages: Record<NetworkAction, { titleKey: string }> = {
  disconnect: {
    titleKey: 'network.dialogs.disconnect',
  },
  'edit-ip': {
    titleKey: 'network.dialogs.editIp',
  },
  'edit-dns': {
    titleKey: 'network.dialogs.editDns',
  },
}

/** 启动时注册所有应用 */
Object.values(applicationRegistry).forEach((descriptor) => {
  windowService.registerApplication(descriptor)
})

const time = ref('00:00:00')
let clockTimer: number | undefined

function updateTime() {
  time.value = new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date())
}

function handleLaunch(applicationId: ApplicationId) {
  const hasWindow = windowService.windows.value.some((window) => window.applicationId === applicationId)
  const window = windowService.open(applicationId)
  if (window) {
    playCue(hasWindow ? 'window-focus' : 'window-open')
  }
  desktop.closeApplicationOverview()
}

function playCue(cue: AudioCue) {
  audioService.play(cue)
}

function handleShowAll() {
  desktop.toggleApplicationOverview()
  playCue('window-focus')
}

function handleCloseOverview() {
  desktop.closeApplicationOverview()
}

/** 电源菜单 → 更改账户 → 清除登录态并跳转登录页 */
function handleSwitchUser() {
  auth.logout()
  creditsStore.reset()
  router.push({ name: 'login' })
}

/**
 * AI 助手窗口的运行时 ID。
 * 暂未用于拦截关闭逻辑（关闭由 AiAssistant 组件内部 onCloseRequest 处理），
 * 保留此引用以便后续可能的窗口操作（如聚焦、最小化等）。
 */
const aiWindowId = ref<string | null>(null)

/** AI 窗口的最小尺寸：屏幕长边的 10% */
const aiMinSize = ref(0)
/** AI 窗口的最大尺寸：屏幕短边的 80% */
const aiMaxSize = ref(0)
/** AI 窗口标题栏文本（聊天消息），由 AiAssistant 通过 onSetTitle 更新 */
const aiTitle = ref('')
/** 右键"问AI"强制覆盖图片 URL，null 时正常轮换 */
const askAiOverrideImage = ref<string | null>(null)

/** Live2D 窗口标题栏文本 — 暂时隐藏 */
// const live2dTitle = ref(t('live2d.idle'))

/** Live2D 窗口的运行时 ID — 暂时隐藏 */
// const live2dWindowId = ref<string | null>(null)

/** ellia 表情图片列表：与语音/台词一一对应（形象统一为 ellia，语音仍用 kei） */
const ELLIA_IMAGES = [
  '/console/images/ellia_little/ellia_normal.png',  // 对应 ogg1 + 台词1
  '/console/images/ellia_little/ellia_happy.png',   // 对应 ogg2 + 台词2
  '/console/images/ellia_little/ellia_angry.png',   // 对应 ogg3 + 台词3
]

/** 标题栏轮换台词：基于 i18n 的 reactive 数组 */
const KEI_TITLES = computed(() => [
  t('aiAssistant.lines.0'),
  t('aiAssistant.lines.1'),
  t('aiAssistant.lines.2'),
])

/** kei 语音文件：点击图片时按 1→2→3→1 循环播放 */
const KEI_VOICES = [
  '/console/sounds/kei/kei_eventmission_2_1.ogg',
  '/console/sounds/kei/kei_eventmission_2_2.ogg',
  '/console/sounds/kei/kei_eventmission_2_3.ogg',
]

/** kei 关闭按钮语音：点击 X 时随机播放 */
const KEI_CLOSE_VOICES = [
  '/console/sounds/kei/kei_给我等着瞧.ogg',
  '/console/sounds/kei/kei_竟敢.ogg',
  '/console/sounds/kei/kei_真是无聊呢.ogg',
]

/** kei 关闭按钮标题栏台词：基于 i18n，与语音一一对应 */
const KEI_CLOSE_TITLES = computed(() => [
  t('aiAssistant.closeLines.0'),
  t('aiAssistant.closeLines.1'),
  t('aiAssistant.closeLines.2'),
])

// ─── Live2D 配置（暂时隐藏 — 取消注释以恢复）──────────────────
/*
const LIVE2D_MODEL_URL = new URL(
  'live2d/qiershazhi_2/qiershazhi_2.model3.json',
  window.location.origin + import.meta.env.BASE_URL,
).toString()
const LIVE2D_IDLE_GROUPS = ['idle', 'idle1', 'idle2', 'idle3', 'idle4', 'idle5', 'idle6']
const LIVE2D_ALL_MOTIONS = [
  'idle', 'idle1', 'idle2', 'idle3', 'idle4', 'idle5', 'idle6',
  'main_1', 'main_2', 'main_3', 'main_4', 'main_5',
  'touch_head', 'touch_body',
  'touch_idle1', 'touch_idle2', 'touch_idle3', 'touch_idle4',
  'touch_idle5', 'touch_idle6', 'touch_idle7', 'touch_idle8',
  'touch_idle9', 'touch_idle10', 'touch_idle11', 'touch_idle12', 'touch_idle13',
  'complete', 'effect', 'home', 'login', 'mail',
  'mission', 'mission_complete', 'touch_special', 'wedding',
]
const LIVE2D_TAP_GROUPS = LIVE2D_ALL_MOTIONS
const LIVE2D_ZONE_GROUPS = {
  head: LIVE2D_ALL_MOTIONS,
  body: LIVE2D_ALL_MOTIONS,
} as const
const LIVE2D_SCALE = 2
const LIVE2D_POSITION = { x: 0.5, y: 0.5 }
const LIVE2D_RENDER_AREA = { x: 0.4, y: 0.4, width: 0.4, height: 0.4 }
*/

/**
 * 初始化 AI 助手窗口。
 *
 * 为什么在 onMounted 中调用而不是在 <template> 中声明？
 * - AI 窗口不是响应式列表驱动的，只需创建一次
 * - 不通过 applicationRegistry 注册，因为不需要出现在 Launchpad 和 DockBar 中
 * - 窗口定位到右下角需要在运行时获取 viewport 尺寸
 *
 * 为什么 controls.close: false？
 * - 关闭行为由 WindowFrame 的 closeAction prop 接管（标题栏 X 按钮→权限拒绝弹窗）
 */
function initAiWindow() {
  // 等比缩放约束：图片 550x550 为 1:1 正方形
  // 最小尺寸 = 屏幕长边的 10%，最大尺寸 = 屏幕短边的 80%
  aiMinSize.value = Math.round(Math.max(window.innerWidth, window.innerHeight) * 0.1)
  aiMaxSize.value = Math.round(Math.min(window.innerWidth, window.innerHeight) * 0.8)
  // 窗口高度含标题栏：550 + 34(titlebar) + 2(border) = 586
  const windowWidth = 552
  const windowHeight = 586
  const padding = 16

  const result = windowService.send({
    type: 'create-window',
    payload: {
      titleKey: 'aiAssistant.title',
      icon: markRaw(Bot),
      component: markRaw(AiAssistant),
      componentProps: {
        images: ELLIA_IMAGES,
        titles: KEI_TITLES.value,
        voices: KEI_VOICES,
        onSetTitle: (text: string) => { aiTitle.value = text },
        get overrideImage() { return askAiOverrideImage.value },
      },
      defaultWidth: windowWidth,
      defaultHeight: windowHeight,
      placement: 'center',   // WindowService.createWindow 仅支持 cascade/center，
      resizable: true,        // 可等比缩放，约束由 WindowFrame 的 aspectRatio/min/max prop 控制
      controls: {
        minimize: false,      // 由 WindowFrame closeAction 在标题栏显示 X（controls.close 保持 false）
        close: false,
      },
      maximizable: false,     // AI 助手为演出型窗口，不允许双击标题栏全屏
      layer: 'ai',            // AI 助手层：常驻于普通窗口之上、模态之下（z-index 固定）
    },
  })

  if (result) {
    aiWindowId.value = result.id
    // 覆写 placement 计算结果，定位到右下角
    result.x = Math.max(0, window.innerWidth - windowWidth - padding)
    result.y = Math.max(0, window.innerHeight - windowHeight - 90) // 90px 留给 DockBar（~46px 高度 + 间距）
  }
}

/**
 * 初始化 Live2D 虚拟形象窗口 — 已归档至 desktop/archive/live2d。
 * 恢复时先移回组件（Live2DAssistant.vue）与资源（public/live2d），
 * 再取消此注释块 + 恢复导入 + 恢复配置常量即可重新启用。
 *
function initLive2dWindow() {
  const windowWidth = 400
  const windowHeight = 434
  const padding = 16

  const result = windowService.send({
    type: 'create-window',
    payload: {
      titleKey: 'live2d.title',
      icon: markRaw(Bot),
      component: markRaw(Live2DAssistant),
      componentProps: {
        modelUrl: LIVE2D_MODEL_URL,
        idleGroups: LIVE2D_IDLE_GROUPS,
        tapGroups: LIVE2D_TAP_GROUPS,
        defaultScaleMultiplier: LIVE2D_SCALE,
        positionRatio: LIVE2D_POSITION,
        renderAreaRatio: LIVE2D_RENDER_AREA,
        zoneMotionGroups: LIVE2D_ZONE_GROUPS,
        onSetTitle: (text: string) => { live2dTitle.value = text },
      },
      defaultWidth: windowWidth,
      defaultHeight: windowHeight,
      placement: 'center',
      resizable: true,
      controls: { minimize: false, close: false },
    },
  })

  if (result) {
    live2dWindowId.value = result.id
    result.x = padding
    result.y = Math.max(0, window.innerHeight - windowHeight - 90)
  }
}
 */

/** AI 窗口是否处于贴合态（贴合跟随需禁用位置过渡，保证跟手） */
const isAiAttached = computed(() => getAiLiaisonState().value === 'attached')

/** AI 窗口标题栏右侧的贴合/分离切换按钮（图标与行为随状态切换） */
const aiTitlebarActions = computed(() => {
  const attached = getAiLiaisonState().value === 'attached'
  return [
    {
      key: 'ai-liaison-toggle',
      label: attached ? t('aiChat.detach') : t('aiChat.attach'),
      icon: attached ? AiDetachIcon : AiAttachIcon,
      onClick: attached ? () => { requestAiDetach() } : () => { requestAiAttach() },
    },
  ]
})

/** AI 窗口 X 按钮 → 贴合态分离；离开态播放关闭语音 + 修改标题栏 + 随机漂移 */
function handleAiCloseRequest() {
  // 贴合态：关闭键语义 = 分离（由 AiAssistant 处理），不走随机漂移
  if (requestAiDetach()) return

  const aiWin = windowService.windows.value.find((w) => w.id === aiWindowId.value)
  if (!aiWin) return

  // 随机选一条关闭台词和语音
  const idx = Math.floor(Math.random() * KEI_CLOSE_VOICES.length)
  audioService.playFile(KEI_CLOSE_VOICES[idx])
  aiTitle.value = KEI_CLOSE_TITLES.value[idx]

  const maxX = window.innerWidth - aiWin.width
  const maxY = window.innerHeight - aiWin.height

  const x = Math.max(0, Math.floor(Math.random() * maxX))
  const y = Math.max(0, Math.floor(Math.random() * maxY))

  // shallowRef 数组 splice 不触发响应式 → 用新数组替换
  windowService.windows.value = windowService.windows.value.map(
    (w) => w.id === aiWin.id ? { ...w, x, y } : w,
  )
}

/** 处理 Live2D 窗口的关闭请求 — 暂时隐藏 */
// function handleLive2dCloseRequest() {
//   handleAiCloseRequest()
// }

/**
 * 电源菜单 → 重启：暂时隐藏 AI 窗口 60 秒后恢复。
 * 不销毁组件实例，保护网络带宽。
 */
let restartTimer: ReturnType<typeof setTimeout> | null = null

function handleRestart() {
  const aiIndex = windowService.windows.value.findIndex((w) => w.id === aiWindowId.value)

  if (aiIndex !== -1) {
    const win = windowService.windows.value[aiIndex]
    // console.log(`[触发] 重启隐藏 → ${win.titleKey}`)
    windowService.windows.value.splice(aiIndex, 1, { ...win, isMinimized: true })
  }

  if (restartTimer) clearTimeout(restartTimer)

  restartTimer = setTimeout(() => {
    const aiIdx = windowService.windows.value.findIndex((w) => w.id === aiWindowId.value)

    if (aiIdx !== -1) {
      const win = windowService.windows.value[aiIdx]
      // console.log(`[触发] 重启恢复 → ${win.titleKey}`)
      windowService.windows.value.splice(aiIdx, 1, { ...win, isMinimized: false })
    }
    restartTimer = null
  }, 60_000)

  // 重启也重置"第一次"标记（与关机一致）：清除目录剧情已播放记录，
  // 下次进入绑定剧情的目录（如 home/形象工程）可重新触发剧情。
  // 成就解锁记录（ellia.desktop.achievement.*）为永久进度，不受影响。
  resetFirstTimeMarkers()
}

/** 电源菜单 → 关机：播放音效 + 弹出权限拒绝弹窗 + 重置"第一次"标记 */
function handleShutdown() {
  // 通过音频通道播放关机音效，10 秒后停止
  audioService.playFile('/console/sounds/shihuai/关羽之歌.mp3')
  setTimeout(() => audioService.stopFile(), 10_000)

  handleAiCloseRequest()

  // 重置"第一次"标记：清除目录剧情已播放记录（localStorage 前缀 ellia.desktop.story.played.）。
  // 关机即视为"新的一天"——下次进入绑定剧情的目录（如 home/形象工程）可重新触发剧情。
  // 注意：该标记存在 localStorage（浏览器 HTTP 缓存禁用不影响它），故单独在此处显式重置；
  // 成就解锁记录（ellia.desktop.achievement.*）为永久进度，不受关机影响。
  resetFirstTimeMarkers()
}

/** 重置"第一次"标记：删除所有 `ellia.desktop.story.played.*` 键 */
function resetFirstTimeMarkers() {
  const prefix = 'ellia.desktop.story.played.'
  const keys: string[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith(prefix)) keys.push(key)
  }
  for (const key of keys) localStorage.removeItem(key)
}

// ─── 右键上下文菜单 ────────────────────────────────────

const contextMenu = reactive({ visible: false, x: 0, y: 0 })

/** 拦截浏览器默认右键菜单，显示自定义菜单 */
function handleContextMenu(e: MouseEvent) {
  e.preventDefault()
  contextMenu.x = e.clientX
  contextMenu.y = e.clientY
  contextMenu.visible = true
}

/** 右键 → 刷新页面 */
function handleRefresh() {
  contextMenu.visible = false
  location.reload()
}

/** 右键 → 问AI：提取选中文字和所在窗口，切换 AI 差分和台词 */
function handleAskAi() {
  contextMenu.visible = false

  const selection = window.getSelection()
  const text = selection?.toString().trim() || ''

  // 查找选中文字所在的窗口（向上遍历 anchorNode 找 .window-frame）
  let windowEl: Element | null = null
  const anchor = selection?.anchorNode
  if (anchor) {
    windowEl = anchor.nodeType === 1
      ? (anchor as Element).closest('.window-frame')
      : anchor.parentElement?.closest('.window-frame') ?? null
  }

  // console.log('[ContextMenu] 选中内容:', text || '(无)')
  // console.log('[ContextMenu] 所在窗口元素:', windowEl)

  // 强制切换 AI 窗口差分和台词
  askAiOverrideImage.value = '/console/images/ellia_little/ellia_happy.png'
  aiTitle.value = 'ellia不知道哦'
}

/** 点击菜单外部关闭 */
function closeContextMenu() {
  contextMenu.visible = false
}

function handleNetworkAction(action: NetworkAction) {
  const message = networkMessages[action]

  windowService.send({
    type: 'create-window',
    payload: {
      titleKey: message.titleKey,
      icon: Info,
      component: MessageBox,
      componentProps: {
        contentComponent: PermissionDenied,
      },
      defaultWidth: 440,
      defaultHeight: 220,
      placement: 'center',
      mode: 'modal',
      resizable: false,
      filters: {
        glitch: true,
      },
      controls: {
        minimize: false,
        close: true,
      },
      maximizable: false,
    },
  })
  playCue('system-alert')
}

function handleWindowClose(windowId: string) {
  const win = windowService.windows.value.find(w => w.id === windowId)
  // console.log(`[触发] 移除窗口 → ${win?.titleKey ?? windowId}`)
  windowService.send({ type: 'close-window', windowId })
  playCue('window-close')
}

function handleWindowFocus(windowId: string) {
  if (windowService.activeWindowId.value !== windowId) {
    playCue('window-focus')
  }
  windowService.send({ type: 'focus-window', windowId })
}

function handleWindowMinimize(windowId: string) {
  const win = windowService.windows.value.find(w => w.id === windowId)
  // console.log(`[触发] 最小化 → ${win?.titleKey ?? windowId}`)
  windowService.send({ type: 'minimize-window', windowId })
  playCue('window-minimize')
}

/** 双击标题栏 → 切换窗口全屏（占据除顶部状态栏外的整个工作区） */
function handleWindowToggleMaximize(windowId: string) {
  windowService.send({ type: 'toggle-maximize-window', windowId })
}

const applicationStates = computed<DockApplicationState[]>(() => {
  const states: DockApplicationState[] = []

  // 注册表应用：按应用 ID 合并去重，一个应用一个条目
  for (const applicationId of windowService.openApplicationIds.value) {
    const windows = windowService.windows.value.filter(
      (window) => window.applicationId === applicationId,
    )
    const hasFocused = windows.some((window) => window.id === windowService.activeWindowId.value)
    const hasForeground = windows.some((window) => !window.isMinimized)

    let state: DockApplicationState['state']
    if (hasFocused && hasForeground) {
      state = 'focused'
    } else if (hasForeground) {
      state = 'foreground'
    } else {
      state = 'minimized'
    }

    states.push({
      applicationId,
      name: t(applicationRegistry[applicationId].titleKey),
      state,
      icon: applicationRegistry[applicationId].icon,
    })
  }

  // 可停靠的独立窗口（文本编辑器等）：每个窗口一个条目，名称取文件名
  for (const window of windowService.windows.value) {
    if (!window.dockable) continue
    const state: DockApplicationState['state'] =
      window.id === windowService.activeWindowId.value && !window.isMinimized
        ? 'focused'
        : !window.isMinimized
          ? 'foreground'
          : 'minimized'

    states.push({
      applicationId: null,
      windowId: window.id,
      name: window.dockTitle ?? window.titleKey,
      state,
      icon: window.icon,
    })
  }

  return states
})

/**
 * 可停靠窗口（文本编辑器）的关闭拦截。
 * 标题栏 X 不再直接关闭，而是委托给编辑器会话：
 * 有未保存修改时由编辑器弹保存提示；无会话（异常情况）时按普通窗口关闭。
 *
 * @param windowId - 目标窗口 ID
 */
function handleDockableWindowClose(windowId: string) {
  if (requestTextEditorClose(windowId)) return
  windowService.send({ type: 'close-window', windowId })
}

function handleDockAppClick(target: DockClickTarget) {
  // 独立窗口条目（文本编辑器）：聚焦或最小化对应窗口
  if (target.windowId) {
    const window = windowService.windows.value.find((w) => w.id === target.windowId)
    if (!window) return
    if (window.id === windowService.activeWindowId.value && !window.isMinimized) {
      handleWindowMinimize(window.id)
    } else {
      handleWindowFocus(window.id)
    }
    return
  }

  const applicationId = target.applicationId
  if (!applicationId) return

  const windows = windowService.windows.value.filter(
    (window) => window.applicationId === applicationId,
  )
  const hasFocused = windows.some((window) => window.id === windowService.activeWindowId.value)
  const hasForeground = windows.some((window) => !window.isMinimized)

  if (hasFocused && hasForeground) {
    const focusedWindow = windows.find((window) => window.id === windowService.activeWindowId.value)
    if (focusedWindow) {
      handleWindowMinimize(focusedWindow.id)
    }
  } else if (hasForeground) {
    const topWindow = windows.slice().sort((a, b) => b.zIndex - a.zIndex)[0]
    if (topWindow) {
      handleWindowFocus(topWindow.id)
    }
  } else {
    handleLaunch(applicationId)
  }
}

/**
 * 浏览器标签页标题管理：
 * - 聚焦虚拟窗口时显示该窗口标题栏文本（与 WindowFrame 的展示逻辑一致）
 * - 整个浏览器标签页被隐藏/失焦（切后台、被覆盖）时显示等待文案
 * - 桌面无聚焦窗口时显示问候文案
 */
const DEFAULT_TAB_TITLE = '你好：我是Ellia！'
const HIDDEN_TAB_TITLE = '我会等你的~'

/** 当前聚焦窗口的标题栏文本，供标签页标题复用 */
const activeWindowTabTitle = computed(() => {
  const win = windowService.activeWindow.value
  if (!win) return null
  return win.title ?? (win.id === aiWindowId.value ? aiTitle.value || undefined : undefined) ?? t(win.titleKey)
})

/** 同步 document.title：隐藏/失焦时显示等待文案，否则显示聚焦窗口标题或问候文案 */
function syncTabTitle() {
  const isHidden = document.visibilityState === 'hidden' || !document.hasFocus()
  document.title = isHidden ? HIDDEN_TAB_TITLE : (activeWindowTabTitle.value ?? DEFAULT_TAB_TITLE)
}

onMounted(() => {
  updateTime()
  clockTimer = window.setInterval(updateTime, 1000)
  void creditsStore.fetchBalances()
  initAiWindow()
  // initLive2dWindow() — Live2D 暂时隐藏

  // 标签页标题：监听焦点/可见性变化 + 聚焦窗口变化
  window.addEventListener('focus', syncTabTitle)
  window.addEventListener('blur', syncTabTitle)
  document.addEventListener('visibilitychange', syncTabTitle)
  watch(activeWindowTabTitle, syncTabTitle)
  syncTabTitle()
})

onBeforeUnmount(() => {
  window.clearInterval(clockTimer)
  if (restartTimer) clearTimeout(restartTimer)
  filterService.destroy(windowGlitchFilter.instanceId)

  window.removeEventListener('focus', syncTabTitle)
  window.removeEventListener('blur', syncTabTitle)
  document.removeEventListener('visibilitychange', syncTabTitle)
})
</script>

<template>
  <main class="desktop-shell" @contextmenu="handleContextMenu" @click="closeContextMenu">
    <DesktopStatusBar :time="time" @network-action="handleNetworkAction" @switch-user="handleSwitchUser" @restart="handleRestart" @shutdown="handleShutdown" />

    <section class="desktop-workspace" aria-label="FakeOS desktop workspace">
      <MatrixRain />
      <div class="workspace-grid" aria-hidden="true"></div>

      <WindowFrame
        v-for="window in windowService.windows.value"
        :key="window.id"
        :window="window"
        :is-active="windowService.activeWindowId.value === window.id"
        :filter-ids="windowFilterIds"
        :body-aspect-ratio="window.id === aiWindowId ? 1 : undefined"
        :min-width="window.id === aiWindowId ? aiMinSize : window.minWidth"
        :min-height="window.id === aiWindowId ? aiMinSize : window.minHeight"
        :max-width="window.id === aiWindowId ? aiMaxSize : window.maxWidth"
        :max-height="window.id === aiWindowId ? aiMaxSize : window.maxHeight"
        :title="window.title ?? (window.id === aiWindowId ? aiTitle : undefined)"
        :close-action="
          window.dockable
            ? () => handleDockableWindowClose(window.id)
            : window.id === aiWindowId
              ? handleAiCloseRequest
              : undefined
        "
        :translucent="window.id === aiWindowId ? true : undefined"
        :skip-enter-animation="window.id === aiWindowId ? true : undefined"
        :on-drag-move="window.id === aiWindowId ? requestAiDragMove : undefined"
        :on-drag-end="window.id === aiWindowId ? requestAiDragEnd : undefined"
        :titlebar-actions="window.id === aiWindowId ? aiTitlebarActions : undefined"
        :instant-move="window.id === aiWindowId ? isAiAttached : undefined"
        @close="handleWindowClose(window.id)"
        @focus="handleWindowFocus(window.id)"
        @minimize="handleWindowMinimize(window.id)"
        @toggle-maximize="handleWindowToggleMaximize(window.id)"
      />
    </section>

    <Transition name="modal-overlay">
      <div v-if="windowService.hasModalWindow.value" class="desktop-modal-overlay" aria-hidden="true"></div>
    </Transition>

    <Transition name="launchpad">
      <Launchpad
        v-if="desktop.isApplicationOverviewOpen"
        :applications="desktop.visibleApplications"
        @close="handleCloseOverview"
        @launch="handleLaunch"
      />
    </Transition>

    <DockBar
      :application-states="applicationStates"
      @click="handleDockAppClick"
      @show-all="handleShowAll"
    />

    <!-- 成就解锁弹窗（Steam 风格右下角通知，模块级队列驱动） -->
    <AchievementToast />

    <!-- 右键自定义菜单 -->
    <div
      v-if="contextMenu.visible"
      class="context-menu"
      :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
      @click.stop
    >
      <button class="context-menu__item" @click="handleRefresh">刷新</button>
      <button class="context-menu__item" @click="handleAskAi">问AI</button>
    </div>
  </main>
</template>

<style scoped>
.desktop-shell {
  position: relative;
  display: grid;
  grid-template-rows: auto 1fr;
  min-height: 100dvh;
  overflow: hidden;
  background: var(--canvas);
}

.desktop-workspace {
  position: relative;
  min-height: 0;
  overflow: hidden;
}

.workspace-grid {
  position: absolute;
  inset: 0;
  opacity: 0.22;
  background-image: linear-gradient(var(--grid-line) 1px, transparent 1px), linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(to bottom, transparent, black 14%, black 88%, transparent);
}

.desktop-modal-overlay {
  position: fixed;
  z-index: 1100;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  background: rgb(0 0 0 / 54%);
}

.modal-overlay-enter-active,
.modal-overlay-leave-active {
  transition: opacity 0.18s ease;
}

.modal-overlay-enter-from,
.modal-overlay-leave-to {
  opacity: 0;
}

.launchpad-enter-active,
.launchpad-leave-active {
  transition: opacity 0.22s ease;
}

.launchpad-enter-from,
.launchpad-leave-to {
  opacity: 0;
}

@media (max-width: 560px) {
  .workspace-grid {
    background-size: 36px 36px;
  }
}

/* ── 右键上下文菜单 ── */
.context-menu {
  position: fixed;
  z-index: 9999;
  min-width: 140px;
  border: 1px solid var(--line-subtle);
  border-radius: 8px;
  background: var(--surface-raised);
  box-shadow: 0 2px 20px rgba(0, 0, 0, 0.35);
  padding: 6px 0;
  overflow: hidden;
  animation: context-enter 0.12s ease-out;
}

@keyframes context-enter {
  from { opacity: 0; transform: scale(0.95) translateY(-4px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}

.context-menu__item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 16px;
  border: none;
  color: var(--text-secondary);
  background: transparent;
  font: 13px/1.4 var(--font-ui);
  text-align: left;
  cursor: pointer;
  transition: background-color 0.12s, color 0.12s;
}

.context-menu__item:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.context-menu__divider {
  height: 1px;
  margin: 4px 8px;
  background: var(--line-subtle);
}
</style>
