<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    stream: MediaStream
    volume?: number
  }>(),
  { volume: 1 },
)

const audioEl = ref<HTMLAudioElement | null>(null)
let retryTimer: number | null = null
let audioContext: AudioContext | null = null
let sourceNode: MediaElementAudioSourceNode | null = null
let gainNode: GainNode | null = null

function setupAudioGraph(): void {
  if (audioContext || !audioEl.value) return
  const AudioContextCtor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!AudioContextCtor) return
  const context = new AudioContextCtor()
  audioContext = context
  sourceNode = context.createMediaElementSource(audioEl.value)
  gainNode = context.createGain()
  sourceNode.connect(gainNode)
  gainNode.connect(context.destination)
  applyVolume()
  if (context.state === 'suspended') {
    void context.resume()
  }
}

function applyVolume(): void {
  const volume = props.volume
  if (gainNode) {
    gainNode.gain.value = volume
  } else if (audioEl.value) {
    audioEl.value.volume = Math.min(1, volume)
  }
}

function tryPlay(): void {
  if (!audioEl.value) return
  const element = audioEl.value
  if (!audioContext) setupAudioGraph()
  if (element.srcObject !== props.stream) {
    element.srcObject = props.stream
  }
  applyVolume()
  if (!element.paused) return
  const playing = element.play()
  if (playing !== undefined) {
    playing
      .then(() => {
        console.log('[voice] audio element playing')
        if (retryTimer !== null) {
          clearTimeout(retryTimer)
          retryTimer = null
        }
      })
      .catch((error) => {
        console.warn('[voice] audio play blocked:', error)
        scheduleRetry()
      })
  }
}

function scheduleRetry(): void {
  if (retryTimer !== null) return
  retryTimer = window.setTimeout(() => {
    retryTimer = null
    tryPlay()
  }, 400)
}

function onUserGesture(): void {
  tryPlay()
}

function bindRetryListeners(): void {
  window.addEventListener('pointerdown', onUserGesture)
  window.addEventListener('touchstart', onUserGesture)
  window.addEventListener('keydown', onUserGesture)
}

function unbindRetryListeners(): void {
  window.removeEventListener('pointerdown', onUserGesture)
  window.removeEventListener('touchstart', onUserGesture)
  window.removeEventListener('keydown', onUserGesture)
}

function applyStream(): void {
  tryPlay()
}

onMounted(() => {
  bindRetryListeners()
  tryPlay()
})

watch(() => props.stream, tryPlay)
watch(
  () => props.volume,
  () => applyVolume(),
)

onBeforeUnmount(() => {
  unbindRetryListeners()
  if (retryTimer !== null) clearTimeout(retryTimer)
  sourceNode?.disconnect()
  gainNode?.disconnect()
  void audioContext?.close()
  audioContext = null
  sourceNode = null
  gainNode = null
})
</script>

<template>
  <audio ref="audioEl" autoplay class="remote-voice-audio" />
</template>

<style scoped>
.remote-voice-audio {
  position: fixed;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
</style>
