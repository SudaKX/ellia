<script setup lang="ts">
import { onBeforeUnmount, onMounted, provide } from 'vue'
import { RouterView } from 'vue-router'

import FilterHost from '@/components/desktop/FilterHost.vue'
import { AudioServiceKey, createAudioService } from '@/composables/useAudioService'
import { createFilterService, FilterServiceKey } from '@/composables/useFilterService'

const filterService = createFilterService()
const filterInstances = filterService.instances
const audioService = createAudioService()

provide(FilterServiceKey, filterService)
provide(AudioServiceKey, audioService)

function unlockAudio() {
  void audioService.unlock()
}

function handleVisibilityChange() {
  if (document.visibilityState === 'hidden') {
    void audioService.suspend()
  }
}

onMounted(() => {
  window.addEventListener('pointerdown', unlockAudio, { capture: true })
  window.addEventListener('keydown', unlockAudio, { capture: true })
  document.addEventListener('visibilitychange', handleVisibilityChange)
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
