<script setup lang="ts">
import { Volume2, VolumeX } from 'lucide-vue-next'

import { useAudioService } from '@/composables/useAudioService'

const audio = useAudioService()

function setMasterVolume(event: Event) {
  audio.setMasterVolume(Number((event.target as HTMLInputElement).value) / 100)
}

function setBusVolume(bus: 'ui' | 'system', event: Event) {
  audio.setBusVolume(bus, Number((event.target as HTMLInputElement).value) / 100)
}
</script>

<template>
  <div class="sound-menu">
    <div class="menu-header">
      <span class="menu-title">Sound</span>
      <button
        class="mute-button"
        type="button"
        :aria-label="audio.isMuted.value ? 'Unmute audio' : 'Mute audio'"
        :title="audio.isMuted.value ? 'Unmute audio' : 'Mute audio'"
        :disabled="!audio.isSupported"
        @click="audio.setMuted(!audio.isMuted.value)"
      >
        <VolumeX v-if="audio.isMuted.value" :size="15" :stroke-width="1.8" />
        <Volume2 v-else :size="15" :stroke-width="1.8" />
      </button>
    </div>

    <p v-if="!audio.isSupported" class="sound-unavailable">Audio is unavailable in this browser.</p>
    <div v-else class="menu-body">
      <label class="volume-control">
        <span>Master</span>
        <input
          type="range"
          min="0"
          max="100"
          step="1"
          :value="Math.round(audio.masterVolume.value * 100)"
          aria-label="Master volume"
          @input="setMasterVolume"
        />
      </label>
      <label class="volume-control">
        <span>Interface</span>
        <input
          type="range"
          min="0"
          max="100"
          step="1"
          :value="Math.round(audio.busVolumes.value.ui * 100)"
          aria-label="Interface volume"
          @input="setBusVolume('ui', $event)"
        />
      </label>
      <label class="volume-control">
        <span>System</span>
        <input
          type="range"
          min="0"
          max="100"
          step="1"
          :value="Math.round(audio.busVolumes.value.system * 100)"
          aria-label="System volume"
          @input="setBusVolume('system', $event)"
        />
      </label>
    </div>
  </div>
</template>

<style scoped>
.sound-menu {
  padding: 12px;
}

.menu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-subtle);
}

.menu-title {
  color: var(--text-primary);
  font: 600 12px var(--font-ui);
}

.mute-button {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 0;
  color: var(--text-secondary);
  background: transparent;
}

.mute-button:hover:not(:disabled) {
  border-color: var(--line-default);
  color: var(--signal-red-soft);
  background: var(--surface-hover);
}

.menu-body {
  display: grid;
  gap: 10px;
}

.volume-control {
  display: grid;
  grid-template-columns: 62px 1fr;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary);
  font: 12px var(--font-ui);
}

.volume-control input {
  width: 100%;
  accent-color: var(--signal-red-soft);
}

.sound-unavailable {
  margin: 0;
  color: var(--text-muted);
  font: 12px var(--font-ui);
}
</style>
