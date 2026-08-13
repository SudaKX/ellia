import { ref } from 'vue'
import { defineStore } from 'pinia'

/**
 * localStorage 键名，持久化全局音量值。
 */
export const MASTER_VOLUME_KEY = 'ellia:master-volume'

function loadVolume(): number {
  try {
    const raw = localStorage.getItem(MASTER_VOLUME_KEY)
    if (raw !== null) {
      const parsed = parseFloat(raw)
      if (!Number.isNaN(parsed)) return Math.max(0, Math.min(1, parsed))
    }
  } catch {
    /* ignore */
  }
  return 0.5
}

/**
 * 全局音量状态。
 *
 * 设计要点：
 * - `masterVolume` 范围 [0, 1]，默认 0.5（50%），从 localStorage 读取上次值。
 * - `setVolume()` 负责 clamp + 四舍五入到两位小数，并自动写回 localStorage。
 * - 所有音效（Web Audio API）和 `<audio>`/`<video>` 元素统一以此值为准。
 *
 * @example
 * ```ts
 * const audio = useAudioStore()
 * audio.setVolume(0.7)  // 设置为 70%
 * ```
 */
export const useAudioStore = defineStore('audio', () => {
  const masterVolume = ref(loadVolume())

  /**
   * 设置全局音量。
   * @param value - 范围 [0, 1]，超出范围会被 clamp。
   */
  function setVolume(value: number) {
    masterVolume.value = Math.round(Math.max(0, Math.min(1, value)) * 100) / 100
    try {
      localStorage.setItem(MASTER_VOLUME_KEY, String(masterVolume.value))
    } catch {
      /* ignore */
    }
  }

  return { masterVolume, setVolume }
})
