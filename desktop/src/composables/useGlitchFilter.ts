import {
  onBeforeUnmount,
  onMounted,
  reactive,
  readonly,
  ref,
  toValue,
  watchEffect,
  type MaybeRefOrGetter,
  type Ref,
} from 'vue'

export interface GlitchOptions {
  seed?: number
  intensity?: number
  frequencyX?: number
  frequencyY?: number
  enableHorizontalDisplacement?: boolean
  enableVerticalDisplacement?: boolean
  animate?: boolean
  frameSkip?: number
}

export interface GlitchState {
  seed: number
  intensity: number
  frequencyX: number
  frequencyY: number
  enableHorizontalDisplacement: boolean
  enableVerticalDisplacement: boolean
}

const CANVAS_WIDTH = 640
const CANVAS_HEIGHT = 360
const DEFAULT_FRAME_SKIP = 24
const DEFAULT_OPTIONS: Required<GlitchOptions> = {
  seed: 0,
  intensity: 30,
  frequencyX: 0.02,
  frequencyY: 0.15,
  enableHorizontalDisplacement: true,
  enableVerticalDisplacement: true,
  animate: false,
  frameSkip: DEFAULT_FRAME_SKIP,
}

export interface GlitchFilterElements {
  mapImage: Ref<SVGFEImageElement | null>
  displacement: Ref<SVGFEDisplacementMapElement | null>
}

export function useGlitchFilter(
  initialOptions: MaybeRefOrGetter<GlitchOptions> = {},
  elements: GlitchFilterElements,
) {
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
  let animationFrameId: number | undefined
  let animationFrameCount = 0

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
      const red = state.enableHorizontalDisplacement ? channel(random, 170) : 128
      const green = state.enableVerticalDisplacement ? channel(random, 28) : 128
      context.fillStyle = `rgb(${red}, ${green}, 128)`
      context.fillRect(0, y, canvas.width, height)

      for (let index = 0; index < fragments; index++) {
        if (random() < 0.4) continue

        const width = Math.round(canvas.width * (0.04 + random() * 0.24))
        const x = Math.round(random() * Math.max(0, canvas.width - width))
        const red = state.enableHorizontalDisplacement ? channel(random, 230) : 128
        const green = state.enableVerticalDisplacement ? channel(random, 64) : 128
        context.fillStyle = `rgb(${red}, ${green}, 128)`
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

  function updateSeed() {
    state.seed = Math.floor(Math.random() * 100_000)
  }

  function resolveFrameSkip() {
    const frameSkip = toValue(initialOptions).frameSkip ?? DEFAULT_FRAME_SKIP
    return Math.max(1, Math.round(frameSkip))
  }

  function animate() {
    animationFrameCount += 1

    if (animationFrameCount % resolveFrameSkip() === 0) {
      updateSeed()
    }

    animationFrameId = window.requestAnimationFrame(animate)
  }

  function startAnimation() {
    if (animationFrameId !== undefined) return

    animationFrameCount = 0
    updateSeed()
    animationFrameId = window.requestAnimationFrame(animate)
  }

  function stopAnimation() {
    if (animationFrameId !== undefined) {
      window.cancelAnimationFrame(animationFrameId)
      animationFrameId = undefined
    }

    animationFrameCount = 0
  }

  onMounted(() => {
    canvas = document.createElement('canvas')
    canvas.width = CANVAS_WIDTH
    canvas.height = CANVAS_HEIGHT
    context = canvas.getContext('2d', { alpha: false })
    mapImage = elements.mapImage.value
    displacement = elements.displacement.value
    isReady.value = Boolean(context && mapImage && displacement)
  })

  watchEffect(() => {
    const options = toValue(initialOptions)
    state.seed = options.seed ?? DEFAULT_OPTIONS.seed
    state.intensity = options.intensity ?? DEFAULT_OPTIONS.intensity
    state.frequencyX = options.frequencyX ?? DEFAULT_OPTIONS.frequencyX
    state.frequencyY = options.frequencyY ?? DEFAULT_OPTIONS.frequencyY
    state.enableHorizontalDisplacement =
      options.enableHorizontalDisplacement ?? DEFAULT_OPTIONS.enableHorizontalDisplacement
    state.enableVerticalDisplacement =
      options.enableVerticalDisplacement ?? DEFAULT_OPTIONS.enableVerticalDisplacement
  })

  watchEffect(() => {
    if (!isReady.value) return
    syncToDOM()
  })

  watchEffect(() => {
    if (isReady.value && toValue(initialOptions).animate) {
      startAnimation()
    } else {
      stopAnimation()
    }
  })

  onBeforeUnmount(() => {
    stopAnimation()
    if (currentUrl) {
      URL.revokeObjectURL(currentUrl)
    }
  })

  return {
    state: readonly(state),
  }
}
