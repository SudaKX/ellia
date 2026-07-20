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
  WindowInstance,
  WindowMessage,
} from '@/types/desktop'

/** 普通窗口 z-index 起点，低于模态窗口但高于桌面元素（如 DockBar 100） */
const NORMAL_Z_INDEX_BASE = 200
/** 模态窗口 z-index 起点，高于普通窗口和 overlay(1100)，确保弹窗不被遮挡 */
const MODAL_Z_INDEX_BASE = 1200
/** 顶部状态栏高度，用于居中计算时扣除偏移 */
const STATUS_BAR_HEIGHT = 40
/** 默认窗口模式 */
const DEFAULT_WINDOW_MODE = 'normal'
/** 默认窗口可调整大小 */
const DEFAULT_WINDOW_RESIZABLE = true
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
    if (mode === 'normal' && hasModalWindow.value) return null

    const position = resolvePosition(payload)

    const id = `win-${++idCounter}`
    const windowInstance: WindowInstance = {
      id,
      applicationId: payload.applicationId ?? null,
      title: payload.title,
      icon: markRaw(payload.icon),
      component: markRaw(payload.component),
      componentProps: payload.componentProps ?? {},
      controls: {
        ...DEFAULT_WINDOW_CONTROLS,
        ...payload.controls,
        minimize: mode === 'modal' ? false : (payload.controls?.minimize ?? true),
      },
      mode,
      resizable: payload.resizable ?? DEFAULT_WINDOW_RESIZABLE,
      filters: { ...payload.filters },
      width: payload.defaultWidth,
      height: payload.defaultHeight,
      x: position.x,
      y: position.y,
      zIndex: mode === 'modal' ? MODAL_Z_INDEX_BASE : NORMAL_Z_INDEX_BASE,
      isMinimized: false,
    }

    windows.value.push(windowInstance)
    promoteToFront(id)
    activeWindowId.value = id
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
    const window = windows.value.find((w) => w.id === windowId)
    if (!window) return

    const topModalWindow = findTopModalWindow()
    if (topModalWindow && topModalWindow.id !== windowId) return

    window.isMinimized = false
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
    const window = windows.value.find((w) => w.id === windowId)
    if (!window || window.mode === 'modal' || !window.controls.minimize || window.isMinimized) return

    window.isMinimized = true

    const index = normalWindowOrder.value.indexOf(windowId)
    if (index !== -1) {
      normalWindowOrder.value.splice(index, 1)
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
  }
}

export type WindowService = ReturnType<typeof useWindowService>
