import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import type { EntityRecord } from '@ellia/puzzle-schema'

import { syncClient } from '../client/ws'

export interface EditorTab {
  entityId: string
  title: string
  componentName: string
}

export const useEditorTabsStore = defineStore('editorTabs', () => {
  const tabs = ref<EditorTab[]>([])
  const activeEntityId = ref<string | null>(null)

  const activeTab = computed(() =>
    tabs.value.find((tab) => tab.entityId === activeEntityId.value) ?? null,
  )
  const tabComponentNames = computed(() => tabs.value.map((tab) => tab.componentName))

  function openTab(entity: EntityRecord, componentName = 'EditorPane'): void {
    const existing = tabs.value.find((tab) => tab.entityId === entity.id)
    if (existing) {
      activeEntityId.value = entity.id
      syncClient.focus(entity.id)
      return
    }
    tabs.value.push({
      entityId: entity.id,
      title: entity.resource_id,
      componentName,
    })
    activeEntityId.value = entity.id
    syncClient.focus(entity.id)
  }

  function activateTab(entityId: string): void {
    if (!tabs.value.some((tab) => tab.entityId === entityId)) return
    activeEntityId.value = entityId
    syncClient.focus(entityId)
  }

  function closeTab(entityId: string): void {
    const index = tabs.value.findIndex((tab) => tab.entityId === entityId)
    if (index < 0) return

    tabs.value.splice(index, 1)
    if (activeEntityId.value === entityId) {
      const next = tabs.value[index] ?? tabs.value[index - 1] ?? null
      activeEntityId.value = next?.entityId ?? null
      if (next) {
        syncClient.focus(next.entityId)
      } else {
        syncClient.focus(null)
      }
    }
  }

  function clear(): void {
    const hadActive = activeEntityId.value !== null
    tabs.value = []
    activeEntityId.value = null
    if (hadActive) syncClient.focus(null)
  }

  return {
    tabs,
    activeEntityId,
    activeTab,
    tabComponentNames,
    openTab,
    activateTab,
    closeTab,
    clear,
  }
})