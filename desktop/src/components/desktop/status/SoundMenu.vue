<script setup lang="ts">
import { Volume2, VolumeX } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

import AudioSpectrum from './AudioSpectrum.vue'
import { useAudioService } from '@/composables/useAudioService'

const audio = useAudioService()
const { t } = useI18n({ useScope: 'global' })

function setMasterVolume(event: Event) {
  audio.setMasterVolume(Number((event.target as HTMLInputElement).value) / 100)
}

function setBusVolume(bus: 'ui' | 'system', event: Event) {
  audio.setBusVolume(bus, Number((event.target as HTMLInputElement).value) / 100)
}

function playVolumePreview() {
  audio.play('window-focus')
}
</script>

<template>
  <div class="sound-menu">
    <div class="menu-header">
      <span class="menu-title">{{ t('sound.title') }}</span>
      <span class="sound-menu__controls">
        <button
          class="sound-menu__icon-button"
          type="button"
          :aria-label="audio.isMuted.value ? t('sound.unmute') : t('sound.mute')"
          :title="audio.isMuted.value ? t('sound.unmute') : t('sound.mute')"
          :disabled="!audio.isSupported"
          @click="audio.setMuted(!audio.isMuted.value)"
        >
          <VolumeX v-if="audio.isMuted.value" :size="15" :stroke-width="1.8" />
          <Volume2 v-else :size="15" :stroke-width="1.8" />
        </button>
      </span>
    </div>

    <p v-if="!audio.isSupported" class="sound-unavailable">{{ t('sound.unavailable') }}</p>
    <div v-else class="menu-body">
      <AudioSpectrum />
      <label class="volume-control">
        <span>{{ t('sound.master') }}</span>
        <input
          type="range"
          min="0"
          max="100"
          step="1"
          :value="Math.round(audio.masterVolume.value * 100)"
          :aria-label="t('sound.masterVolume')"
          @input="setMasterVolume"
          @change="playVolumePreview"
        />
      </label>
      <label class="volume-control">
        <span>{{ t('sound.interface') }}</span>
        <input
          type="range"
          min="0"
          max="100"
          step="1"
          :value="Math.round(audio.busVolumes.value.ui * 100)"
          :aria-label="t('sound.interfaceVolume')"
          @input="setBusVolume('ui', $event)"
          @change="playVolumePreview"
        />
      </label>
      <label class="volume-control">
        <span>{{ t('sound.system') }}</span>
        <input
          type="range"
          min="0"
          max="100"
          step="1"
          :value="Math.round(audio.busVolumes.value.system * 100)"
          :aria-label="t('sound.systemVolume')"
          @input="setBusVolume('system', $event)"
          @change="playVolumePreview"
        />
      </label>
    </div>
  </div>
</template>

<style scoped>
.sound-menu {
  width: min(420px, calc(100vw - 24px));
  padding: 16px;
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

.sound-menu__controls {
  display: flex;
  gap: 4px;
}

.sound-menu__icon-button {
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

.sound-menu__icon-button:hover:not(:disabled) {
  border-color: var(--line-default);
  color: var(--signal-red-soft);
  background: var(--surface-hover);
}

.menu-body {
  display: grid;
  gap: 14px;
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
