<script setup lang="ts">
import { Volume2 } from 'lucide-vue-next'
import { useAudioStore } from '@/stores/audio'
import { useAudio } from '@/composables/useAudio'

const audio = useAudioStore()
const { playTone } = useAudio()

/** 滑块松手时播放提示音，频率随音量升高（200Hz → 800Hz），柔和反馈当前音量大小。 */
function previewVolume(event: Event) {
  const target = event.target as HTMLInputElement
  const vol = target.valueAsNumber
  const freq = 200 + vol * 600 // 0%→200Hz, 100%→800Hz
  playTone(freq, 180, 0.1)
}
</script>

<template>
  <div class="sound-menu">
    <div class="menu-header">
      <Volume2 :size="14" :stroke-width="1.8" />
      <span
        class="menu-title"
        :class="{
          'menu-title--muted': audio.masterVolume === 0,
          'menu-title--max': audio.masterVolume === 1,
        }"
      >
        {{ audio.masterVolume === 0 ? '已将Ellia禁言' : audio.masterVolume === 1 ? '捏哈哈哈' : 'Sound' }}
      </span>
    </div>
    <div class="menu-body">
      <div class="volume-row">
        <input
          type="range"
          class="volume-slider"
          min="0"
          max="1"
          step="0.01"
          :value="audio.masterVolume"
          @input="audio.setVolume(($event.target as HTMLInputElement).valueAsNumber)"
          @change="previewVolume"
        />
        <span class="volume-value">{{ Math.round(audio.masterVolume * 100) }}%</span>
      </div>
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
  gap: 6px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-subtle);
  color: var(--text-secondary);
}

.menu-title {
  color: var(--text-primary);
  font: 600 12px var(--font-ui);
}

.menu-title--muted {
  color: var(--signal-red);
}

.menu-title--max {
  color: #f08dac;
}

.volume-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.volume-slider {
  flex: 1;
  height: 4px;
  appearance: none;
  border-radius: 2px;
  background: var(--line-default);
  outline: none;
}

.volume-slider::-webkit-slider-thumb {
  width: 12px;
  height: 12px;
  appearance: none;
  border-radius: 50%;
  background: var(--signal-red-soft);
  cursor: pointer;
}

.volume-slider::-moz-range-thumb {
  width: 12px;
  height: 12px;
  border: none;
  border-radius: 50%;
  background: var(--signal-red-soft);
  cursor: pointer;
}

.volume-value {
  min-width: 36px;
  text-align: right;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 12px;
}
</style>
