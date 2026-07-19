import { computed, markRaw, ref, shallowRef, triggerRef } from 'vue'

import type {
  ApplicationDescriptor,
  ApplicationId,
  CreateWindowPayload,
  WindowInstance,
  WindowMessage,
} from '@/types/desktop'

const NORMAL_Z_INDEX_BASE = 200
const MODAL_Z_INDEX_BASE = 1200
const STATUS_BAR_HEIGHT = 40
const DEFAULT_WINDOW_MODE = 'normal'
const DEFAULT_WINDOW_RESIZABLE = true
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
