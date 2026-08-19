<script setup lang="ts">
import { useVoiceStore } from '../../stores/voice'
import RemoteVoiceAudio from './RemoteVoiceAudio.vue'

const voice = useVoiceStore()
</script>

<template>
  <RemoteVoiceAudio
    v-for="(stream, participantId) in voice.remoteStreams"
    :key="participantId"
    :stream="stream"
    :volume="voice.speakerVolume"
  />
</template>
