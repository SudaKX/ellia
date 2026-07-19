import { computed, markRaw, ref, shallowRef, triggerRef } from 'vue'

import type { ApplicationDescriptor, ApplicationId, WindowInstance } from '@/types/desktop'

const Z_INDEX_BASE = 200

export function useWindowService() {
  const registry = shallowRef<Map<ApplicationId, ApplicationDescriptor>>(new Map())
  const windows = shallowRef<WindowInstance[]>([])
  const windowOrder = ref<string[]>([])
  const activeWindowId = ref<string | null>(null)
  let idCounter = 0

  const openApplicationIds = computed(() => {
    const ids = new Set<ApplicationId>()
    for (const window of windows.value) {
      ids.add(window.applicationId)
    }
    return Array.from(ids)
  })

  const activeWindow = computed(() => {
    if (!activeWindowId.value) return null
    return windows.value.find((window) => window.id === activeWindowId.value) ?? null
  })

  function assignZIndexes() {
    windows.value.forEach((window) => {
      const index = windowOrder.value.indexOf(window.id)
      window.zIndex = Z_INDEX_BASE + index
    })
    triggerRef(windows)
  }

  function promoteToFront(windowId: string) {
    const index = windowOrder.value.indexOf(windowId)
    if (index !== -1) {
      windowOrder.value.splice(index, 1)
    }
    windowOrder.value.push(windowId)
    assignZIndexes()
  }

  function registerApplication(descriptor: ApplicationDescriptor) {
    registry.value.set(descriptor.id, descriptor)
  }

  function createWindow(applicationId: ApplicationId): WindowInstance | null {
    const descriptor = registry.value.get(applicationId)
    if (!descriptor) return null

    const id = `win-${++idCounter}`
    const window: WindowInstance = {
      id,
      applicationId,
      title: descriptor.title,
      icon: markRaw(descriptor.icon),
      component: markRaw(descriptor.component),
      width: descriptor.defaultWidth,
      height: descriptor.defaultHeight,
      x: 80 + (windows.value.length * 30) % 200,
      y: 80 + (windows.value.length * 30) % 150,
      zIndex: Z_INDEX_BASE,
      isMinimized: false,
    }

    windows.value.push(window)
    promoteToFront(id)
    activeWindowId.value = id
    return window
  }

  function open(applicationId: ApplicationId): WindowInstance | null {
    const existing = windows.value
      .filter((window) => window.applicationId === applicationId)
      .sort((a, b) => b.zIndex - a.zIndex)[0]
    if (existing) {
      focus(existing.id)
      return existing
    }
    return createWindow(applicationId)
  }

  function focus(windowId: string) {
    const window = windows.value.find((w) => w.id === windowId)
    if (!window) return

    window.isMinimized = false
    promoteToFront(windowId)
    activeWindowId.value = windowId
  }

  function close(windowId: string) {
    const index = windows.value.findIndex((w) => w.id === windowId)
    if (index === -1) return

    windows.value.splice(index, 1)

    const orderIndex = windowOrder.value.indexOf(windowId)
    if (orderIndex !== -1) {
      windowOrder.value.splice(orderIndex, 1)
    }

    assignZIndexes()

    if (activeWindowId.value === windowId) {
      activeWindowId.value = findTopNonMinimizedWindow()
    }
  }

  function minimize(windowId: string) {
    const window = windows.value.find((w) => w.id === windowId)
    if (!window || window.isMinimized) return

    window.isMinimized = true

    const index = windowOrder.value.indexOf(windowId)
    if (index !== -1) {
      windowOrder.value.splice(index, 1)
      windowOrder.value.unshift(windowId)
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
    const topId = windowOrder.value
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
    openApplicationIds,
    registerApplication,
    open,
    close,
    focus,
    minimize,
    restore,
  }
}

export type WindowService = ReturnType<typeof useWindowService>
