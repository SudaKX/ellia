<script setup lang="ts">
import { computed } from 'vue'

import { useVoiceStore } from '../../stores/voice'

const voice = useVoiceStore()

const channelName = computed(
  () =>
    voice.channels.find((channel) => channel.id === voice.currentChannelId)?.name ?? '语音频道',
)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="voice.currentChannelId && voice.participants.length"
      class="voice-speaker-overlay"
    >
      <div class="voice-speaker-overlay__channel">{{ channelName }}</div>
      <div class="voice-speaker-overlay__members">
        <span
          v-for="participant in voice.participants"
          :key="participant.id"
          class="voice-speaker-overlay__member"
          :class="{ 'voice-speaker-overlay__member--speaking': voice.speakers[participant.id] }"
        >
          {{ participant.username }}
        </span>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.voice-speaker-overlay {
  position: fixed;
  right: 12px;
  bottom: 12px;
  z-index: 900;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  max-width: 220px;
  padding: 8px 10px;
  background: transparent;
}

.voice-speaker-overlay__channel {
  font-size: 0.75rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.voice-speaker-overlay__members {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.voice-speaker-overlay__member {
  padding: 0 10px;
  border-radius: 999px;
  line-height: 1.8;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font-size: 0.78rem;
  opacity: 0.45;
  transition: opacity 0.15s ease;
}

.voice-speaker-overlay__member--speaking {
  background: var(--md-sys-color-primary, #6750a4);
  color: var(--md-sys-color-on-primary, #ffffff);
  opacity: 1;
}
</style>
