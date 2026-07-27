<script setup lang="ts">
import { onBeforeUnmount, onMounted, provide, watch } from 'vue'
import { RouterView } from 'vue-router'

import FilterHost from '@/components/desktop/FilterHost.vue'
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
  document.addEventListener('visibilitychange', handleVisibilityChange)

  // 预热 Live2D 资源到浏览器缓存 — 暂时隐藏，恢复 Live2D 时取消注释
  // const base = window.location.origin + import.meta.env.BASE_URL
  // const textureUrl = new URL('live2d/qiershazhi_2/textures/texture_00.webp', base).toString()
  // requestIdleCallback(() => { fetch(textureUrl) }, { timeout: 2000 })
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', unlockAudio, { capture: true })
  window.removeEventListener('keydown', unlockAudio, { capture: true })
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  void audioService.dispose()
})
</script>

<template>
  <FilterHost :instances="filterInstances" @ready="filterService.markReady" />
  <RouterView />
</template>
