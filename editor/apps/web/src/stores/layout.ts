import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const LAYOUT_STORAGE_PREFIX = 'ellia:layout:'

function storageKey(projectId: string): string {
  return `${LAYOUT_STORAGE_PREFIX}${projectId}`
}

export interface LayoutWidths {
  leftWidth: number
  rightWidth: number
}

function defaults(): LayoutWidths {
  return { leftWidth: 400, rightWidth: 400 }
}

function readStoredWidths(projectId: string): LayoutWidths {
  try {
    const raw = localStorage.getItem(storageKey(projectId))
    if (!raw) return defaults()
    const parsed = JSON.parse(raw) as Partial<LayoutWidths>
    return {
      leftWidth: typeof parsed.leftWidth === 'number' ? parsed.leftWidth : defaults().leftWidth,
      rightWidth: typeof parsed.rightWidth === 'number' ? parsed.rightWidth : defaults().rightWidth,
    }
  } catch {
    return defaults()
  }
}

export const useLayoutStore = defineStore('layout', () => {
  const projectId = ref<string | null>(null)
  const leftWidth = ref<number>(defaults().leftWidth)
  const rightWidth = ref<number>(defaults().rightWidth)

  function initialize(nextProjectId: string): void {
    if (projectId.value === nextProjectId) return
    projectId.value = nextProjectId
    const widths = readStoredWidths(nextProjectId)
    leftWidth.value = widths.leftWidth
    rightWidth.value = widths.rightWidth
  }

  function setLeftWidth(width: number): void {
    leftWidth.value = width
    scheduleSave()
  }

  function setRightWidth(width: number): void {
    rightWidth.value = width
    scheduleSave()
  }

  let saveTimer: ReturnType<typeof setTimeout> | null = null
  function scheduleSave(): void {
    if (!projectId.value) return
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = setTimeout(() => {
      try {
        localStorage.setItem(
          storageKey(projectId.value!),
          JSON.stringify({ leftWidth: leftWidth.value, rightWidth: rightWidth.value }),
        )
      } catch (error) {
        console.warn('[layout] localStorage 写入失败：', error)
      }
      saveTimer = null
    }, 300)
  }

  watch([leftWidth, rightWidth], () => {
    scheduleSave()
  })

  return {
    projectId,
    leftWidth,
    rightWidth,
    initialize,
    setLeftWidth,
    setRightWidth,
  }
})