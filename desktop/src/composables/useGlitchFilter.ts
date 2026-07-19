import { onBeforeUnmount, onMounted, reactive, readonly, ref, watchEffect } from 'vue'

export interface GlitchOptions {
  seed?: number
  intensity?: number
  frequencyX?: number
  frequencyY?: number
}

export interface GlitchState {
  seed: number
  intensity: number
  frequencyX: number
  frequencyY: number
}

const CANVAS_WIDTH = 640
const CANVAS_HEIGHT = 360
const DEFAULT_OPTIONS: Required<GlitchOptions> = {
  seed: 0,
  intensity: 30,
  frequencyX: 0.02,
  frequencyY: 0.15,
}

export function useGlitchFilter(initialOptions: GlitchOptions = {}) {
  const state = reactive<GlitchState>({
    ...DEFAULT_OPTIONS,
    ...initialOptions,
  })

  const isReady = ref(false)
  let canvas: HTMLCanvasElement | null = null
  let context: CanvasRenderingContext2D | null = null
  let mapImage: SVGFEImageElement | null = null
  let displacement: SVGFEDisplacementMapElement | null = null
  let currentUrl: string | null = null
  let mapVersion = 0

  function createRandom(seed: number) {
    return () => {
      seed |= 0
      seed = (seed + 0x6d2b79f5) | 0
      let value = Math.imul(seed ^ (seed >>> 15), 1 | seed)
      value = (value + Math.imul(value ^ (value >>> 7), 61 | value)) ^ value
      return ((value ^ (value >>> 14)) >>> 0) / 4294967296
    }
  }

  function channel(random: () => number, spread: number) {
    return Math.max(0, Math.min(255, Math.round(128 + (random() - 0.5) * spread)))
  }

  function resolveBandDensity() {
    return Math.max(4, Math.min(96, Math.round(state.frequencyY * 280)))
  }

  function resolveFragmentCount() {
    return Math.max(1, Math.min(24, Math.round(state.frequencyX * 2000)))
  }

  function drawMap() {
    if (!canvas || !context) return

    const random = createRandom(state.seed)
    const density = resolveBandDensity()
    const fragments = resolveFragmentCount()
    const bandHeight = Math.max(2, Math.round(canvas.height / density))

    context.fillStyle = 'rgb(128, 128, 128)'
    context.fillRect(0, 0, canvas.width, canvas.height)

    for (let y = 0; y < canvas.height;) {
      const height = Math.max(2, Math.round(bandHeight * (0.25 + random() * 1.7)))
      context.fillStyle = `rgb(${channel(random, 170)}, ${channel(random, 28)}, 128)`
      context.fillRect(0, y, canvas.width, height)

      for (let index = 0; index < fragments; index++) {
        if (random() < 0.4) continue

        const width = Math.round(canvas.width * (0.04 + random() * 0.24))
        const x = Math.round(random() * Math.max(0, canvas.width - width))
        context.fillStyle = `rgb(${channel(random, 230)}, ${channel(random, 64)}, 128)`
        context.fillRect(x, y, width, height)
      }

      y += height
    }
  }

  function writeMapUrl() {
    if (!canvas || !mapImage) return

    const version = ++mapVersion
    canvas.toBlob((blob) => {
      if (!blob) return

      const nextUrl = URL.createObjectURL(blob)
      if (version !== mapVersion || !mapImage) {
        URL.revokeObjectURL(nextUrl)
        return
      }

      const previousUrl = currentUrl
      mapImage.setAttribute('href', nextUrl)
      currentUrl = nextUrl

      if (previousUrl) {
        window.setTimeout(() => URL.revokeObjectURL(previousUrl), 800)
      }
    }, 'image/png')
  }

  function syncToDOM() {
    if (!displacement) return

    displacement.setAttribute('scale', (state.intensity * 0.0015).toFixed(3))
    drawMap()
    writeMapUrl()
  }

  function randomizeSeed() {
    state.seed = Math.floor(Math.random() * 100_000)
  }

  function setIntensity(value: number) {
    state.intensity = value
  }

  function setFrequency(x: number, y: number) {
    state.frequencyX = x
    state.frequencyY = y
  }

  onMounted(() => {
    canvas = document.createElement('canvas')
    canvas.width = CANVAS_WIDTH
    canvas.height = CANVAS_HEIGHT
    context = canvas.getContext('2d', { alpha: false })
    mapImage = document.getElementById('glitch-canvas-map') as SVGFEImageElement | null
    displacement = document.getElementById('glitch-displacement') as SVGFEDisplacementMapElement | null
    isReady.value = Boolean(context && mapImage && displacement)
  })

  watchEffect(() => {
    if (!isReady.value) return
    syncToDOM()
  })

  onBeforeUnmount(() => {
    if (currentUrl) {
      URL.revokeObjectURL(currentUrl)
    }
  })

  return {
    state: readonly(state),
    randomizeSeed,
    setIntensity,
    setFrequency,
  }
}

export type GlitchFilterController = ReturnType<typeof useGlitchFilter>
