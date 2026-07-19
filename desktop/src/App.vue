<script setup lang="ts">
import { onMounted, provide, watch } from 'vue'
import { RouterView } from 'vue-router'

import FilterHost from '@/components/desktop/FilterHost.vue'
import { createFilterService, FilterServiceKey } from '@/composables/useFilterService'
import { useAudioStore } from '@/stores/audio'

const filterService = createFilterService()
const filterInstances = filterService.instances

provide(FilterServiceKey, filterService)

const audio = useAudioStore()

/**
 * 将全局音量同步到页面中所有 <audio> / <video> 元素。
 * 音效走 Web Audio API（useAudio composable），不经过此函数。
 */
function syncMediaVolume() {
  const els = document.querySelectorAll<HTMLMediaElement>('audio, video')
  els.forEach((el) => {
    el.volume = audio.masterVolume
  })
}

watch(() => audio.masterVolume, syncMediaVolume)

// 存在动态插入 <video> 的可能性（尽管很少），用 MutationObserver 兜底。
onMounted(() => {
  const observer = new MutationObserver(() => syncMediaVolume())
  observer.observe(document.body, { childList: true, subtree: true })
})
</script>

<template>
  <FilterHost :instances="filterInstances" @ready="filterService.markReady" />
  <RouterView />
</template>
