<script setup lang="ts">
import { onBeforeUnmount, onMounted, provide, watch } from 'vue'
import { RouterView } from 'vue-router'

import FilterHost from '@/components/desktop/FilterHost.vue'
import { handleGlobalSaveShortcut } from '@/composables/useTextEditorSession'
import { AudioServiceKey, createAudioService } from '@/composables/useAudioService'
import { createFilterService, FilterServiceKey } from '@/composables/useFilterService'
import { useAudioStore } from '@/stores/audio'

const filterService = createFilterService()
const filterInstances = filterService.instances
const audioService = createAudioService()

provide(FilterServiceKey, filterService)
provide(AudioServiceKey, audioService)

const audio = useAudioStore()

/**
 * 将全局音量同步到页面中所有 <audio> / <video> 元素。
 * 音效走 Web Audio API（useAudioService），不经过此函数。
 */
function syncMediaVolume() {
  const els = document.querySelectorAll<HTMLMediaElement>('audio, video')
  els.forEach((el) => {
    el.volume = audio.masterVolume
  })
}

watch(() => audio.masterVolume, syncMediaVolume)

function unlockAudio() {
  void audioService.unlock()
}

/**
 * 全局键盘拦截：禁止 Tab 焦点切换与浏览器前进/后退快捷键。
 *
 * - `Ctrl/Cmd+S`：全局覆盖保存快捷键——焦点在文本编辑器内 → 触发保存；
 *   焦点不在任何编辑器 → 无动作（两者都不会触发浏览器"保存网页"）。
 *   监听只在这里注册一次，由 useTextEditorSession 的注册表定位目标编辑器。
 * - `Tab`：阻止焦点逃逸出 FakeOS（游戏桌面场景，不希望焦点切到地址栏/浏览器 UI）
 * - `Alt+← / Alt+→`：浏览器历史前进/后退
 * - `Backspace`：旧版 Chrome/Edge 中在非输入控件上按 Backspace 会触发后退；
 *   输入控件（input/textarea/select/contenteditable）中放行，保证正常删字
 *
 * 为什么用 capture + preventDefault：在事件捕获阶段拦截，能阻止浏览器默认导航行为。
 */
function blockNavigationKeys(event: KeyboardEvent) {
  // 全局覆盖 Ctrl/Cmd+S：编辑器有焦点才保存，否则无动作；一律阻止浏览器保存网页
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    event.preventDefault()
    handleGlobalSaveShortcut(event)
    return
  }

  if (event.key === 'Tab') {
    event.preventDefault()
    return
  }

  if (event.altKey && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
    event.preventDefault()
    return
  }

  if (event.key === 'Backspace') {
    const target = event.target as HTMLElement | null
    const isEditable =
      target?.isContentEditable === true ||
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement
    if (!isEditable) {
      event.preventDefault()
    }
  }
}

function handleVisibilityChange() {
  if (document.visibilityState === 'hidden') {
    void audioService.suspend()
  }
}

// 存在动态插入 <video> 的可能性（尽管很少），用 MutationObserver 兜底。
onMounted(() => {
  const observer = new MutationObserver(() => syncMediaVolume())
  observer.observe(document.body, { childList: true, subtree: true })
  window.addEventListener('pointerdown', unlockAudio, { capture: true })
  window.addEventListener('keydown', unlockAudio, { capture: true })
  window.addEventListener('keydown', blockNavigationKeys, { capture: true })
  document.addEventListener('visibilitychange', handleVisibilityChange)

  // 预热 Live2D 资源到浏览器缓存 — 暂时隐藏，恢复 Live2D 时取消注释
  // const base = window.location.origin + import.meta.env.BASE_URL
  // const textureUrl = new URL('live2d/qiershazhi_2/textures/texture_00.webp', base).toString()
  // requestIdleCallback(() => { fetch(textureUrl) }, { timeout: 2000 })
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', unlockAudio, { capture: true })
  window.removeEventListener('keydown', unlockAudio, { capture: true })
  window.removeEventListener('keydown', blockNavigationKeys, { capture: true })
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  void audioService.dispose()
})
</script>

<template>
  <FilterHost :instances="filterInstances" @ready="filterService.markReady" />
  <RouterView />
</template>
