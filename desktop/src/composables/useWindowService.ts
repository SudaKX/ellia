/**
 * # 窗口管理服务 (WindowService)
 *
 * FakeOS 的核心服务，管理桌面窗口的完整生命周期。
 *
 * ## 架构
 *
 * ```
 * WindowService
 *  │
 *  ├─ registry: Map<ApplicationId, ApplicationDescriptor>
 *  │     └─ 按需注册的应用模板（通过 registerApplication()）
 *  │
 *  ├─ windows: WindowInstance[]
 *  │     └─ 当前所有窗口实例（响应式 shallowRef）
 *  │
 *  ├─ normalWindowOrder: string[]    (普通窗口层级栈)
 *  ├─ modalWindowOrder: string[]     (模态窗口层级栈)
 *  │     └─ 双层 z-index 管理，模态窗口永远在普通窗口之上
 *  │
 *  └─ activeWindowId / activeWindow  (当前聚焦窗口)
 * ```
 *
 * ## 双层 z-index 设计
 *
 * - **普通窗口**：z-index 从 `NORMAL_Z_INDEX_BASE(200)` 递增
 * - **模态窗口**：z-index 从 `MODAL_Z_INDEX_BASE(1200)` 递增
 * - 存在模态窗口时，普通窗口的 focus 操作被忽略
 * - 模态窗口关闭后，自动回退焦点到最顶层的普通窗口
 *
 * ## 消息总线 (WindowMessage)
 *
 * `send()` 方法提供统一的消息入口，支持四种操作：
 * - `create-window`：根据 `CreateWindowPayload` 创建窗口
 * - `close-window`：关闭窗口
 * - `minimize-window`：最小化窗口
 * - `focus-window`：聚焦窗口
 *
 * 消息总线的好处：组件通过 emit 事件传递消息字符串即可，
 * 无需直接依赖 WindowService 实例，降低耦合。
 *
 * ## 使用方式
 *
 * ```ts
 * const ws = useWindowService()
 *
 * // 1. 注册应用
 * ws.registerApplication({ id: 'terminal', title: 'Terminal', ... })
 *
 * // 2. 打开应用（单例）
 * ws.open('terminal')
 *
 * // 3. 创建自定义窗口（如网络断开弹窗）
 * ws.send({ type: 'create-window', payload: { mode: 'modal', ... } })
 * ```
 */

import { computed, markRaw, ref, shallowRef, triggerRef } from 'vue'

import type {
  ApplicationDescriptor,
  ApplicationId,
  CreateWindowPayload,
  WindowBounds,
  WindowInstance,
  WindowMessage,
} from '@/types/desktop'

/** 普通窗口 z-index 起点，低于模态窗口但高于桌面元素（如 DockBar 100） */
const NORMAL_Z_INDEX_BASE = 200
/** 模态窗口 z-index 起点，高于普通窗口和 overlay(1100)，确保弹窗不被遮挡 */
const MODAL_Z_INDEX_BASE = 1200
/**
 * AI 助手窗口 z-index 起点，介于普通窗口与模态窗口之间。
 * 语义："第二层级"——高于普通窗口、低于警告提示栏/模态弹窗。
 */
const AI_Z_INDEX_BASE = 1000
/** 顶部状态栏高度，用于居中计算时扣除偏移 */
const STATUS_BAR_HEIGHT = 40
/** 默认窗口模式 */
const DEFAULT_WINDOW_MODE = 'normal'
/** 默认窗口可调整大小 */
const DEFAULT_WINDOW_RESIZABLE = true
/** 默认允许双击标题栏切换全屏 */
const DEFAULT_MAXIMIZABLE = true
/** 默认窗口控件配置 */
const DEFAULT_WINDOW_CONTROLS = {
  minimize: true,
  close: true,
}

export function useWindowService() {
  const registry = shallowRef<Map<ApplicationId, ApplicationDescriptor>>(new Map())
  const windows = shallowRef<WindowInstance[]>([])
  const normalWindowOrder = ref<string[]>([])
  const modalWindowOrder = ref<string[]>([])
  const activeWindowId = ref<string | null>(null)
  let idCounter = 0

  const openApplicationIds = computed(() => {
    const ids = new Set<ApplicationId>()
    for (const window of windows.value) {
      if (window.applicationId) {
        ids.add(window.applicationId)
      }
    }
    return Array.from(ids)
  })

  const activeWindow = computed(() => {
    if (!activeWindowId.value) return null
    return windows.value.find((window) => window.id === activeWindowId.value) ?? null
  })

  const hasModalWindow = computed(() => modalWindowOrder.value.length > 0)

  function assignZIndexes() {
    normalWindowOrder.value.forEach((windowId, index) => {
      const window = windows.value.find((candidate) => candidate.id === windowId)
      if (window) {
        window.zIndex = NORMAL_Z_INDEX_BASE + index
      }
    })

    modalWindowOrder.value.forEach((windowId, index) => {
      const window = windows.value.find((candidate) => candidate.id === windowId)
      if (window) {
        window.zIndex = MODAL_Z_INDEX_BASE + index
      }
    })
    triggerRef(windows)
  }

  function promoteToFront(windowId: string) {
    const window = windows.value.find((candidate) => candidate.id === windowId)
    if (!window) return

    const order = window.mode === 'modal' ? modalWindowOrder.value : normalWindowOrder.value
    const index = order.indexOf(windowId)
    if (index !== -1) {
      order.splice(index, 1)
    }
    order.push(windowId)
    assignZIndexes()
  }

  function registerApplication(descriptor: ApplicationDescriptor) {
    registry.value.set(descriptor.id, descriptor)
  }

  function findTopModalWindow(): WindowInstance | null {
    for (const windowId of modalWindowOrder.value.slice().reverse()) {
      const window = windows.value.find((candidate) => candidate.id === windowId)
      if (window?.mode === 'modal') {
        return window
      }
    }
    return null
  }

  function resolvePosition(payload: CreateWindowPayload) {
    if (payload.placement === 'center') {
      return {
        x: Math.max(0, Math.round((window.innerWidth - payload.defaultWidth) / 2)),
        y: Math.max(
          0,
          Math.round((window.innerHeight - STATUS_BAR_HEIGHT - payload.defaultHeight) / 2),
        ),
      }
    }

    return {
      x: 80 + (windows.value.length * 30) % 200,
      y: 80 + (windows.value.length * 30) % 150,
    }
  }

  function createWindow(payload: CreateWindowPayload): WindowInstance | null {
    const mode = payload.mode ?? DEFAULT_WINDOW_MODE
    const layer = payload.layer ?? (mode === 'modal' ? 'modal' : 'normal')
    // AI 层窗口不受模态阻断影响（常驻于普通窗口之上、模态之下）
    if (mode === 'normal' && hasModalWindow.value && layer !== 'ai') return null

    const position = resolvePosition(payload)

    const id = `win-${++idCounter}`
    const windowInstance: WindowInstance = {
      id,
      applicationId: payload.applicationId ?? null,
      titleKey: payload.titleKey,
      title: payload.title,
      icon: markRaw(payload.icon),
      component: markRaw(payload.component),
      componentProps: payload.componentProps ?? {},
      controls: {
        ...DEFAULT_WINDOW_CONTROLS,
        ...payload.controls,
        minimize: layer === 'ai' ? false : (mode === 'modal' ? false : (payload.controls?.minimize ?? true)),
      },
      mode,
      layer,
      resizable: payload.resizable ?? DEFAULT_WINDOW_RESIZABLE,
      minWidth: payload.minWidth,
      minHeight: payload.minHeight,
      maxWidth: payload.maxWidth,
      maxHeight: payload.maxHeight,
      filters: { ...payload.filters },
      dockable: payload.dockable ?? false,
      dockTitle: payload.dockTitle,
      maximizable: payload.maximizable ?? DEFAULT_MAXIMIZABLE,
      isMaximized: false,
      restoreBounds: undefined,
      width: payload.defaultWidth,
      height: payload.defaultHeight,
      x: position.x,
      y: position.y,
      zIndex: layer === 'ai'
        ? AI_Z_INDEX_BASE
        : (mode === 'modal' ? MODAL_Z_INDEX_BASE : NORMAL_Z_INDEX_BASE),
      isMinimized: false,
    }

    windows.value.push(windowInstance)
    if (layer === 'ai') {
      // AI 层窗口 z-index 固定，不参与层级重排，直接聚焦
      activeWindowId.value = id
    } else {
      promoteToFront(id)
      activeWindowId.value = id
    }
    return windowInstance
  }

  function send(message: WindowMessage): WindowInstance | null | void {
    switch (message.type) {
      case 'create-window':
        return createWindow(message.payload)
      case 'close-window':
        close(message.windowId)
        return
      case 'minimize-window':
        minimize(message.windowId)
        return
      case 'focus-window':
        focus(message.windowId)
        return
      case 'toggle-maximize-window':
        toggleMaximize(message.windowId)
        return
    }
  }

  function open(applicationId: ApplicationId): WindowInstance | null {
    const existing = windows.value
      .filter((window) => window.applicationId === applicationId)
      .sort((a, b) => b.zIndex - a.zIndex)[0]
    if (existing) {
      focus(existing.id)
      return existing
    }

    const descriptor = registry.value.get(applicationId)
    if (!descriptor) return null

    return (
      send({
        type: 'create-window',
        payload: {
          ...descriptor,
          applicationId,
        },
      }) ?? null
    )
  }

  function focus(windowId: string) {
    const idx = windows.value.findIndex((w) => w.id === windowId)
    if (idx === -1) return
    const window = windows.value[idx]

    // AI 层窗口：恢复最小化后直接聚焦，不参与层级重排（z-index 固定）
    if (window.layer === 'ai') {
      if (window.isMinimized) {
        // splice 创建新对象以触发 shallowRef 响应式（直接 mutate 属性无效）
        windows.value.splice(idx, 1, { ...window, isMinimized: false })
      }
      activeWindowId.value = windowId
      return
    }

    const topModalWindow = findTopModalWindow()
    if (topModalWindow && topModalWindow.id !== windowId) return

    if (window.isMinimized) {
      // splice 创建新对象以触发 shallowRef 响应式（直接 mutate 属性无效）
      windows.value.splice(idx, 1, { ...window, isMinimized: false })
    }
    promoteToFront(windowId)
    activeWindowId.value = windowId
  }

  function close(windowId: string) {
    const index = windows.value.findIndex((w) => w.id === windowId)
    if (index === -1) return
    const window = windows.value[index]
    if (!window.controls.close) return

    windows.value.splice(index, 1)

    const order = window.mode === 'modal' ? modalWindowOrder.value : normalWindowOrder.value
    const orderIndex = order.indexOf(windowId)
    if (orderIndex !== -1) {
      order.splice(orderIndex, 1)
    }

    assignZIndexes()

    if (activeWindowId.value === windowId) {
      activeWindowId.value = findTopNonMinimizedWindow()
    }
  }

  function minimize(windowId: string) {
    const index = windows.value.findIndex((w) => w.id === windowId)
    if (index === -1) return
    const window = windows.value[index]
    if (window.mode === 'modal' || !window.controls.minimize || window.isMinimized) return

    // splice 创建新对象以触发 shallowRef 响应式（直接 mutate 属性无效）
    windows.value.splice(index, 1, { ...window, isMinimized: true })

    const orderIndex = normalWindowOrder.value.indexOf(windowId)
    if (orderIndex !== -1) {
      normalWindowOrder.value.splice(orderIndex, 1)
      normalWindowOrder.value.unshift(windowId)
    }
    assignZIndexes()

    if (activeWindowId.value === windowId) {
      activeWindowId.value = findTopNonMinimizedWindow()
    }
  }

  function restore(windowId: string) {
    focus(windowId)
  }

  /**
   * 双击标题栏触发：切换窗口全屏。
   *
   * 全屏 = 占据除顶部状态栏（STATUS_BAR_HEIGHT）外的整个工作区。
   * 进入全屏前保存原几何到 restoreBounds，退出时恢复。
   * 通过 splice 创建新对象以触发 shallowRef 响应式（直接 mutate 无效）。
   *
   * 注意：WindowFrame 的本地宽高 ref 通过 watch 同步，见 WindowFrame.vue。
   *
   * @param windowId - 目标窗口 ID
   */
  function toggleMaximize(windowId: string) {
    const index = windows.value.findIndex((w) => w.id === windowId)
    if (index === -1) return
    const win = windows.value[index]
    // 演出型窗口（maximizable: false）或最小化窗口不允许全屏
    if (!win.maximizable || win.isMinimized) return

    if (!win.isMaximized) {
      const restoreBounds: WindowBounds = {
        x: win.x,
        y: win.y,
        width: win.width,
        height: win.height,
      }
      windows.value.splice(index, 1, {
        ...win,
        isMaximized: true,
        restoreBounds,
        x: 0,
        y: 0,
        width: globalThis.innerWidth,
        height: globalThis.innerHeight - STATUS_BAR_HEIGHT,
      })
    } else {
      const bounds = win.restoreBounds ?? { x: 0, y: 0, width: 480, height: 360 }
      windows.value.splice(index, 1, {
        ...win,
        isMaximized: false,
        restoreBounds: undefined,
        x: bounds.x,
        y: bounds.y,
        width: bounds.width,
        height: bounds.height,
      })
    }
    triggerRef(windows)
  }

  function findTopNonMinimizedWindow(): string | null {
    const topModalWindow = findTopModalWindow()
    if (topModalWindow) return topModalWindow.id

    const topId = normalWindowOrder.value
      .slice()
      .reverse()
      .find((id) => {
        const window = windows.value.find((w) => w.id === id)
        return window && !window.isMinimized
      })
    return topId ?? null
  }

  return {
    windows,
    activeWindowId,
    activeWindow,
    hasModalWindow,
    openApplicationIds,
    registerApplication,
    send,
    open,
    close,
    focus,
    minimize,
    restore,
    toggleMaximize,
  }
}

export type WindowService = ReturnType<typeof useWindowService>
