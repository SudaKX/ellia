<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAudioService } from '@/composables/useAudioService'

const BAR_COUNT = 48

const { t } = useI18n({ useScope: 'global' })
const audio = useAudioService()
const canvasRef = ref<HTMLCanvasElement | null>(null)
const samples = new Uint8Array(audio.spectrumSize)

let animationFrameId: number | undefined
let resizeObserver: ResizeObserver | undefined

function resizeCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return

  const pixelRatio = window.devicePixelRatio || 1
  const { width, height } = canvas.getBoundingClientRect()
  const nextWidth = Math.max(1, Math.round(width * pixelRatio))
  const nextHeight = Math.max(1, Math.round(height * pixelRatio))

  if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
    canvas.width = nextWidth
    canvas.height = nextHeight
  }
}

function drawSpectrum() {
  const canvas = canvasRef.value
  const context = canvas?.getContext('2d')
  if (!canvas || !context) return

  const pixelRatio = window.devicePixelRatio || 1
  const width = canvas.width / pixelRatio
  const height = canvas.height / pixelRatio
  const hasSamples = audio.readSpectrumData(samples)
  const gap = 2
  const barWidth = Math.max(1, (width - gap * (BAR_COUNT - 1)) / BAR_COUNT)

  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
  context.clearRect(0, 0, width, height)
  context.fillStyle = getComputedStyle(canvas).getPropertyValue('--signal-red').trim() || '#e34d55'

  for (let barIndex = 0; barIndex < BAR_COUNT; barIndex += 1) {
    const start = Math.floor((barIndex / BAR_COUNT) * samples.length)
    const end = Math.max(start + 1, Math.floor(((barIndex + 1) / BAR_COUNT) * samples.length))
    let sum = 0

    for (let sampleIndex = start; sampleIndex < end; sampleIndex += 1) {
      sum += hasSamples ? samples[sampleIndex] : 0
    }

    const intensity = sum / (end - start) / 255
    const barHeight = Math.max(1, Math.pow(intensity, 0.65) * height)
    const x = barIndex * (barWidth + gap)
    const y = (height - barHeight) / 2

    context.globalAlpha = intensity > 0.005 ? 0.95 : 0.2
    context.fillRect(x, y, barWidth, barHeight)
  }

  context.globalAlpha = 1
  animationFrameId = window.requestAnimationFrame(drawSpectrum)
}

onMounted(() => {
  resizeCanvas()
  resizeObserver = new ResizeObserver(resizeCanvas)
  resizeObserver.observe(canvasRef.value!)
  animationFrameId = window.requestAnimationFrame(drawSpectrum)
})

onBeforeUnmount(() => {
  if (animationFrameId !== undefined) {
    window.cancelAnimationFrame(animationFrameId)
  }
  resizeObserver?.disconnect()
})
</script>

<template>
  <canvas
    ref="canvasRef"
    class="audio-spectrum"
    role="img"
    :aria-label="t('sound.spectrumLabel')"
  ></canvas>
</template>

<style scoped>
.audio-spectrum {
  display: block;
  width: 100%;
  height: 56px;
  border: 1px solid var(--line-subtle);
}
</style>
