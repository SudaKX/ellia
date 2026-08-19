import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface TooltipPosition {
  left: string
  top: string
}

export interface ShowTooltipOptions {
  text: string
  /** 以该元素为锚点，tooltip 水平居中并显示在其下方 */
  anchor?: HTMLElement | null
  /** 锚点下方偏移，默认 8px */
  offset?: number
  /** 显式视口坐标（优先级高于 anchor） */
  x?: number
  y?: number
}

export const useTooltipStore = defineStore('tooltip', () => {
  const visible = ref(false)
  const text = ref('')
  const position = ref<TooltipPosition | null>(null)

  function show(options: ShowTooltipOptions): void {
    text.value = options.text
    const offset = options.offset ?? 8

    if (options.x !== undefined && options.y !== undefined) {
      position.value = {
        left: `${options.x}px`,
        top: `${options.y}px`,
      }
    } else if (options.anchor) {
      const rect = options.anchor.getBoundingClientRect()
      position.value = {
        left: `${rect.left + rect.width / 2}px`,
        top: `${rect.bottom + offset}px`,
      }
    } else {
      position.value = null
    }

    visible.value = true
  }

  function showAt(x: number, y: number, textValue: string, offset = 0): void {
    show({ text: textValue, x, y, offset })
  }

  function hide(): void {
    visible.value = false
  }

  return {
    visible,
    text,
    position,
    show,
    showAt,
    hide,
  }
})
