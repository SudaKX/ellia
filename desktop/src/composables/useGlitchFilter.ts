/**
 * # Glitch 故障滤镜引擎
 *
 * 通过 SVG feDisplacementMap + feColorMatrix 实现色差故障效果。
 *
 * ## 渲染管线
 *
 * ```
 * Canvas (320×180 噪声图)
 *   → toBlob → ObjectURL → HTMLImageElement (预加载)
 *   → feImage 注入 SVG 滤镜
 *   → feDisplacementMap (用噪声图 R/G 通道偏移 SourceGraphic)
 *   → feColorMatrix (分离 R/G/B 三通道)
 *   → feOffset (红通道左移、绿通道右移，产生色差)
 *   → feBlend (screen 混合，重组三通道)
 * ```
 *
 * ## 关键设计决策
 *
 * ### 帧池 (Frame Pool)
 * 预生成 64 帧噪声图（FRAME_COUNT），按 frameSkip 间隔切换。
 * 而非每帧实时渲染——因为 Canvas → Blob → Image 的异步链路在 60fps 下无法完成。
 *
 * ### idleCallback 调度
 * 帧池构建使用 `requestIdleCallback`（降级到 setTimeout(0)），
 * 确保生成过程不影响 UI 交互响应。
 * 当参数变化时，`poolVersion` 自增使旧构建任务主动废弃。
 *
 * ### 色差偏移 (Chromatic Aberration)
 * 通过 `feOffset` 的 dx 参数控制红/绿通道水平偏移量：
 * - redOffset.dx 设为 -chromaticAberration
 * - greenOffset.dx 设为 +chromaticAberration
 * 蓝通道不偏移，视觉上产生 CRT 显示器的色散效果。
 *
 * ### ready Promise
 * 返回 `ready: Promise<void>`，在帧池构建完毕后 resolve。
 * 父组件可以 `await ready` 确保滤镜初始帧就绪后再展示内容。
 *
 * ## 使用方式
 *
 * ```ts
 * const { state, ready } = useGlitchFilter(options, {
 *   mapImage: ref<SVGFEImageElement>(),
 *   displacement: ref<SVGFEDisplacementMapElement>(),
 *   redOffset: ref<SVGFEOffsetElement>(),
 *   greenOffset: ref<SVGFEOffsetElement>(),
 * })
 *
 * // 运行时修改参数
 * filterService.update(instanceId, { intensity: 20, animate: true })
 * ```
 *
 * ## 与 darksky 分支区别
 *
 * 本分支保留了色差偏移 (chromaticAberration) 和帧池 (frame pool)。
 * darksky 分支移除了这些，仅保留基础位移效果。
 * 保留完整版因为色差是 Glitch 美学的核心视觉特征。
 */

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
  chromaticAberration?: number
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
  chromaticAberration: number
}

export interface GlitchFilterElements {
  mapImage: Ref<SVGFEImageElement | null>
  displacement: Ref<SVGFEDisplacementMapElement | null>
  redOffset: Ref<SVGFEOffsetElement | null>
  greenOffset: Ref<SVGFEOffsetElement | null>
}

interface GlitchFrame {
  url: string
  image: HTMLImageElement
}

type IdleCallbackWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number
  cancelIdleCallback?: (handle: number) => void
}

const CANVAS_WIDTH = 320
const CANVAS_HEIGHT = 180
const FRAME_COUNT = 64
const DEFAULT_FRAME_SKIP = 24
const DEFAULT_OPTIONS: Required<GlitchOptions> = {
  seed: 0,
  intensity: 30,
  frequencyX: 0.02,
  frequencyY: 0.15,
  enableHorizontalDisplacement: true,
  enableVerticalDisplacement: true,
  chromaticAberration: 0.001,
  animate: false,
  frameSkip: DEFAULT_FRAME_SKIP,
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
  const isPoolReady = ref(false)
  let resolveReady: () => void = () => undefined
  let hasResolvedReady = false
  const ready = new Promise<void>((resolve) => {
    resolveReady = resolve
  })

  let canvas: HTMLCanvasElement | null = null
  let context: CanvasRenderingContext2D | null = null
  let mapImage: SVGFEImageElement | null = null
  let displacement: SVGFEDisplacementMapElement | null = null
  let redOffset: SVGFEOffsetElement | null = null
  let greenOffset: SVGFEOffsetElement | null = null
  let framePool: GlitchFrame[] = []
  let currentFrameIndex = 0
  let poolVersion = 0
  let idleCallbackId: number | undefined
  let idleCallbackUsesIdleApi = false
  let idleResolve: (() => void) | undefined
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

  function resolveBandDensity(options: GlitchState) {
    return Math.max(4, Math.min(96, Math.round(options.frequencyY * 280)))
  }

  function resolveFragmentCount(options: GlitchState) {
    return Math.max(1, Math.min(24, Math.round(options.frequencyX * 2000)))
  }

  function drawMap(seed: number, options: GlitchState) {
    if (!canvas || !context) return

    const random = createRandom(seed)
    const density = resolveBandDensity(options)
    const fragments = resolveFragmentCount(options)
    const bandHeight = Math.max(2, Math.round(canvas.height / density))

    context.fillStyle = 'rgb(128, 128, 128)'
    context.fillRect(0, 0, canvas.width, canvas.height)

    for (let y = 0; y < canvas.height;) {
      const height = Math.max(2, Math.round(bandHeight * (0.25 + random() * 1.7)))
      const red = options.enableHorizontalDisplacement ? channel(random, 170) : 128
      const green = options.enableVerticalDisplacement ? channel(random, 28) : 128
      context.fillStyle = `rgb(${red}, ${green}, 128)`
      context.fillRect(0, y, canvas.width, height)

      for (let index = 0; index < fragments; index++) {
        if (random() < 0.4) continue

        const width = Math.round(canvas.width * (0.04 + random() * 0.24))
        const x = Math.round(random() * Math.max(0, canvas.width - width))
        const fragmentRed = options.enableHorizontalDisplacement ? channel(random, 230) : 128
        const fragmentGreen = options.enableVerticalDisplacement ? channel(random, 64) : 128
        context.fillStyle = `rgb(${fragmentRed}, ${fragmentGreen}, 128)`
        context.fillRect(x, y, width, height)
      }

      y += height
    }
  }

  function createMapBlob() {
    if (!canvas) return Promise.resolve<Blob | null>(null)

    return new Promise<Blob | null>((resolve) => {
      canvas?.toBlob(resolve, 'image/png')
    })
  }

  async function preload(url: string) {
    const image = new Image()
    image.src = url

    try {
      await image.decode()
    } catch {
      // Keep the image reference even when decode is unavailable.
    }

    return image
  }

  function waitForIdle() {
    return new Promise<void>((resolve) => {
      const idleWindow = window as IdleCallbackWindow
      const finish = () => {
        idleCallbackId = undefined
        idleCallbackUsesIdleApi = false
        idleResolve = undefined
        resolve()
      }

      idleResolve = finish
      if (idleWindow.requestIdleCallback) {
        idleCallbackUsesIdleApi = true
        idleCallbackId = idleWindow.requestIdleCallback(finish, { timeout: 200 })
      } else {
        idleCallbackUsesIdleApi = false
        idleCallbackId = window.setTimeout(finish, 0)
      }
    })
  }

  function cancelPendingIdleWork() {
    if (idleCallbackId === undefined) return

    const idleWindow = window as IdleCallbackWindow
    if (idleCallbackUsesIdleApi) {
      idleWindow.cancelIdleCallback?.(idleCallbackId)
    } else {
      window.clearTimeout(idleCallbackId)
    }

    idleCallbackId = undefined
    idleCallbackUsesIdleApi = false
    idleResolve?.()
    idleResolve = undefined
  }

  function revokeFrames(frames: GlitchFrame[]) {
    frames.forEach((frame) => URL.revokeObjectURL(frame.url))
  }

  function clearFramePool() {
    mapImage?.removeAttribute('href')
    revokeFrames(framePool)
    framePool = []
    currentFrameIndex = 0
    isPoolReady.value = false
  }

  function displayFrame(index: number) {
    if (!mapImage || framePool.length === 0) return

    currentFrameIndex = index % framePool.length
    mapImage.setAttribute('href', framePool[currentFrameIndex].url)
  }

  function resolveFrameSkip() {
    const frameSkip = toValue(initialOptions).frameSkip ?? DEFAULT_FRAME_SKIP
    return Math.max(1, Math.round(frameSkip))
  }

  async function buildFramePool(version: number, options: GlitchState) {
    const frames: GlitchFrame[] = []

    for (let index = 0; index < FRAME_COUNT; index++) {
      await waitForIdle()
      if (version !== poolVersion) {
        revokeFrames(frames)
        return
      }

      drawMap(options.seed + index * 0x9e3779b1, options)
      const blob = await createMapBlob()
      if (version !== poolVersion) {
        revokeFrames(frames)
        return
      }
      if (!blob) continue

      const url = URL.createObjectURL(blob)
      const image = await preload(url)
      if (version !== poolVersion) {
        URL.revokeObjectURL(url)
        revokeFrames(frames)
        return
      }

      frames.push({ url, image })
    }

    if (version !== poolVersion) {
      revokeFrames(frames)
      return
    }

    framePool = frames
    displayFrame(0)
    isPoolReady.value = framePool.length > 0

    if (!hasResolvedReady) {
      hasResolvedReady = true
      resolveReady()
    }
  }

  function rebuildFramePool() {
    const version = ++poolVersion
    cancelPendingIdleWork()
    clearFramePool()
    void buildFramePool(version, { ...state })
  }

  function syncToDOM() {
    if (!displacement) return
    displacement.setAttribute('scale', (state.intensity * 0.0015).toFixed(3))
    redOffset?.setAttribute('dx', (-state.chromaticAberration).toFixed(4))
    greenOffset?.setAttribute('dx', state.chromaticAberration.toFixed(4))
  }

  function animate() {
    animationFrameCount += 1

    if (animationFrameCount % resolveFrameSkip() === 0) {
      displayFrame(currentFrameIndex + 1)
    }

    animationFrameId = window.requestAnimationFrame(animate)
  }

  function startAnimation() {
    if (animationFrameId !== undefined) return

    animationFrameCount = 0
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
    redOffset = elements.redOffset.value
    greenOffset = elements.greenOffset.value
    isReady.value = Boolean(context && mapImage && displacement)

    if (!isReady.value && !hasResolvedReady) {
      hasResolvedReady = true
      resolveReady()
    }
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
    state.chromaticAberration = options.chromaticAberration ?? DEFAULT_OPTIONS.chromaticAberration
  })

  watchEffect(() => {
    if (!isReady.value) return
    syncToDOM()
    rebuildFramePool()
  })

  watchEffect(() => {
    if (isReady.value && isPoolReady.value && toValue(initialOptions).animate) {
      startAnimation()
    } else {
      stopAnimation()
    }
  })

  onBeforeUnmount(() => {
    poolVersion += 1
    cancelPendingIdleWork()
    stopAnimation()
    clearFramePool()

    if (!hasResolvedReady) {
      hasResolvedReady = true
      resolveReady()
    }
  })

  return {
    state: readonly(state),
    ready,
  }
}
