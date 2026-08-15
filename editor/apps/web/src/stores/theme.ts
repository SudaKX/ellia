import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'ellia-theme'

function systemPrefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function readInitialMode(): ThemeMode {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    // localStorage 不可用时回退到系统偏好
  }
  return systemPrefersDark() ? 'dark' : 'light'
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(readInitialMode())

  function apply(modeToApply: ThemeMode): void {
    document.documentElement.dataset.theme = modeToApply
  }

  function initialize(): void {
    apply(mode.value)
  }

  function setMode(next: ThemeMode): void {
    mode.value = next
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // 偏好持久化失败不阻断主题切换
    }
    apply(next)
  }

  function toggle(): void {
    setMode(mode.value === 'light' ? 'dark' : 'light')
  }

  return { mode, initialize, setMode, toggle }
})
