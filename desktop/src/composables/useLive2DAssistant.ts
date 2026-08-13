import { ref } from 'vue'
import * as PIXI from 'pixi.js'
import { Application } from 'pixi.js'
import { Live2DModel, MotionPriority } from '@jannchie/pixi-live2d-display/cubism4'

/**
 * # useLive2DAssistant — Live2D 运行时封装
 *
 * 基于参考实现 `vue3-live2d-package` 的增强版 composable，
 * 负责 PixiJS Application 的完整生命周期、模型加载、resize 适配、
 * motion 播放和分区交互。
 *
 * ## 使用前提
 *
 * 1. 已安装 `pixi.js` 和 `@jannchie/pixi-live2d-display`
 * 2. `live2dcubismcore.min.js` 已在 `index.html` 中预加载
 * 3. 模型资源已放入 `public/live2d/<model-name>/`
 *
 * ## 为什么用 composable 而不是指令
 *
 * Live2D 运行时包含多个状态（ready、error、模型引用），
 * composable 的响应式 ref 天然适合 Vue 组件绑定。
 */

type Live2DWindow = Window & typeof globalThis & {
  PIXI?: typeof PIXI
  Live2DCubismCore?: unknown
}

export type HitZone = 'head' | 'body'

export interface UseLive2DAssistantOptions {
  container: HTMLElement
  modelUrl: string
  coreScriptUrl: string
  idleGroups: string[]
  tapGroups: string[]
  defaultScaleMultiplier?: number
  positionRatio?: { x: number; y: number }
  /** 可视区域：截取模型哪一块区域映射到容器（x/y 为起点比例，width/height 为区域比例） */
  renderAreaRatio?: { x: number; y: number; width: number; height: number }
  zoneMotionGroups?: Partial<Record<HitZone, string[]>>
}

interface ModelBounds {
  x: number
  y: number
  width: number
  height: number
}

const CUBISM_CORE_SCRIPT_ID = 'live2d-cubism-core'
let cubismCorePromise: Promise<void> | null = null

/** 模块级缓存：按 modelUrl 分组，每个模型只初始化一次，后续复用 */
interface Live2DCache {
  app: Application
  model: Live2DModel
  baseBounds: ModelBounds
}
const modelCache = new Map<string, Live2DCache>()

export function useLive2DAssistant(options: UseLive2DAssistantOptions) {
  const ready = ref(false)
  const error = ref<string | null>(null)

  let app: Application | null = null
  let model: Live2DModel | null = null
  let baseBounds: ModelBounds | null = null

  const defaultScaleMultiplier = options.defaultScaleMultiplier ?? 1
  const positionRatio = options.positionRatio ?? { x: 0.5, y: 0.5 }
  /** 可视区域：截取模型哪一块映射到容器（默认全区域） */
  const renderAreaRatio = options.renderAreaRatio ?? { x: 0, y: 0, width: 1, height: 1 }

  /** 每个动作组的独立轮播 cursor，避免 touch_head 影响 main 的播放顺序 */
  const motionCursors = new Map<string, number>()

  function clampRatio(value: number) {
    return Math.min(1, Math.max(0, value))
  }

  function getSequenceCursor(key: string, length: number) {
    if (length <= 0) return 0
    const nextIndex = motionCursors.get(key) ?? 0
    motionCursors.set(key, (nextIndex + 1) % length)
    return nextIndex % length
  }

  function toUserMessage(err: unknown): string {
    if (err instanceof Error) {
      if (err.message.toLowerCase().includes('webgl')) return '当前浏览器环境不支持 WebGL'
    }
    return '模型资源加载失败'
  }

  function getWindowRef(): Live2DWindow {
    return window as Live2DWindow
  }

  /**
   * 确保 Cubism Core 运行时已加载。
   * 正常情况下 `index.html` 已预加载（通过 `<script>` 标签），
   * 此函数作为兜底：如果预加载失败，动态注入 script 标签。
   */
  async function ensureCubismCoreLoaded(src: string) {
    const win = getWindowRef()
    if (win.Live2DCubismCore) return

    if (!cubismCorePromise) {
      cubismCorePromise = new Promise<void>((resolve, reject) => {
        const existing = document.getElementById(CUBISM_CORE_SCRIPT_ID) as HTMLScriptElement | null
        if (existing) {
          existing.addEventListener('load', () => resolve(), { once: true })
          existing.addEventListener('error', () => reject(new Error('Live2D 运行时加载失败')), { once: true })
          return
        }
        const script = document.createElement('script')
        script.id = CUBISM_CORE_SCRIPT_ID
        script.async = true
        script.src = src
        script.addEventListener('load', () => resolve(), { once: true })
        script.addEventListener('error', () => reject(new Error('Live2D 运行时加载失败')), { once: true })
        document.head.appendChild(script)
      }).catch((err) => {
        cubismCorePromise = null
        throw err
      })
    }
    await cubismCorePromise
  }

  async function initialize() {
    try {
      ready.value = false
      error.value = null

      // 模块级缓存：该 modelUrl 已初始化过 → 直接复用
      const cached = modelCache.get(options.modelUrl)
      if (cached) {
        app = cached.app
        model = cached.model
        baseBounds = cached.baseBounds
        options.container.replaceChildren(app.canvas)
        resize()
        ready.value = true
        return
      }

      await ensureCubismCoreLoaded(options.coreScriptUrl)

      const win = getWindowRef()
      win.PIXI = PIXI

      // 初始化 PixiJS Application（强制 WebGL——Live2D Cubism 不支持 WebGPU）
      app = new Application()
      await app.init({
        antialias: true,
        autoDensity: true,
        backgroundAlpha: 0,
        height: Math.max(options.container.clientHeight, 1),
        preference: 'webgl',
        /** 生产环境下纹理 alpha 预乘会导致模型边缘白边 */
        premultipliedAlpha: false,
        resolution: Math.max(window.devicePixelRatio, 1),
        width: Math.max(options.container.clientWidth, 1),
        /** 防止 WebGL 上下文在窗口失焦/缩放时被销毁导致纹理引用失效 */
        preserveDrawingBuffer: true,
      })

      // 禁用 PixiJS 8 内置纹理 GC —— 它会删除 Cubism 仍在引用的贴图
      const r = app.renderer as Record<string, any>
      for (const key of ['textureGC', '_textureGC', 'textureGarbageCollector']) {
        if (r[key]) { r[key].active = false; r[key].maxIdle = Infinity }
      }

      app.canvas.style.display = 'block'
      app.canvas.style.width = '100%'
      app.canvas.style.height = '100%'
      options.container.replaceChildren(app.canvas)

      // 处理 WebGL 上下文丢失/恢复：preventDefault 阻止浏览器销毁上下文
      app.canvas.addEventListener('webglcontextlost', (e) => {
        // console.warn('[Live2D] WebGL context lost, attempting restore')
        e.preventDefault()
      })
      app.canvas.addEventListener('webglcontextrestored', () => {
        // console.info('[Live2D] WebGL context restored')
      })

      // 加载 Live2D 模型（Cubism 4）
      model = await Live2DModel.from(options.modelUrl, {
        idleMotionGroup: options.idleGroups[0] ?? 'idle',
        onError: (loadError) => { throw loadError },
        ticker: PIXI.Ticker.shared,
      })

      model.eventMode = 'none'
      app.stage.addChild(model)

      // 获取模型原始边界，用于后续缩放计算
      model.scale.set(1)
      const initialBounds = model.getLocalBounds()
      baseBounds = {
        x: initialBounds.minX,
        y: initialBounds.minY,
        width: initialBounds.width,
        height: initialBounds.height,
      }

      resize()

      /**
       * 防止 PixiJS 8 RenderGroup 在模型 idle 时回收 WebGL 纹理。
       *
       * 根因：PixiJS 8 的 RenderGroupSystem 将模型渲染缓存为纹理，
       * 模型停止动画约 2 分钟后系统认为缓存"过期"并 deleteTexture，
       * 但 Cubism 渲染器仍持有该纹理引用 → bindTexture: deleted object。
       *
       * 修复：每帧标记 RenderGroup 为脏 + 每 2 秒微调 Cubism 参数，
       * 双重保障阻止 PixiJS 释放纹理。
       */
      let secCounter = 0
       const idleCursor = { value: 0 }
       PIXI.Ticker.shared.add(() => {
        if (!model) return

        // 1. 每帧强制 RenderGroup 标记为需要更新 → 阻止纹理回收
        const m = model as any
        if (m._renderGroup) m._renderGroup._needsUpdate = true

        // 2. 每 2 秒对 Cubism 内部参数做一次微小变动 → 真正的视觉变化
        secCounter += PIXI.Ticker.shared.elapsedMS
        const internal = m.internalModel
        if (internal?.coreModel && secCounter > 2000) {
          secCounter = 0
          const val = Math.random() * 0.002
          internal.coreModel.setParameterValueById('ParamAngleX', val)
          internal.coreModel.setParameterValueById('ParamAngleY', val)
        }

        // 3. 每 8 秒切换一次待机动作
        idleCursor.value += PIXI.Ticker.shared.elapsedMS
        if (idleCursor.value > 8000 && options.idleGroups.length > 1) {
          idleCursor.value = 0
          const group = options.idleGroups[Math.floor(Math.random() * options.idleGroups.length)]
          model.motion(group, undefined, MotionPriority.IDLE)
        }
      })

      // 播放初始待机动作
      if (options.idleGroups.length > 0) {
        await model.motion(options.idleGroups[0], undefined, MotionPriority.IDLE)
      }

      // 存入模块级缓存
      modelCache.set(options.modelUrl, { app, model, baseBounds })

      ready.value = true
    } catch (err) {
      console.error('[Live2D] initialize failed', err)
      error.value = toUserMessage(err)
      ready.value = false
    }
  }

  /**
   * 容器尺寸变化时重新计算模型缩放和位置。
   * 核心逻辑：以 `positionRatio` 为模型中心锚点，按容器尺寸等比缩放。
   */
  function resize() {
    if (!app || !model || !baseBounds) return
    // 防止在 WebGL 上下文丢失期间触发 resize 导致纹理失效
    const gl = (app.renderer as PIXI.WebGLRenderer).gl
    if (gl?.isContextLost?.()) return

    const nextWidth = Math.max(options.container.clientWidth, 1)
    const nextHeight = Math.max(options.container.clientHeight, 1)

    app.renderer.resize(nextWidth, nextHeight)

    // 可视区域：按 renderAreaRatio 截取模型区域映射到容器
    const areaX = clampRatio(renderAreaRatio.x)
    const areaY = clampRatio(renderAreaRatio.y)
    const areaWidth = Math.max(nextWidth * clampRatio(renderAreaRatio.width), 1)
    const areaHeight = Math.max(nextHeight * clampRatio(renderAreaRatio.height), 1)
    const areaLeft = nextWidth * areaX
    const areaTop = nextHeight * areaY

    // 模型基础缩放：取 82% 容器尺寸做适配，再乘以缩放倍数
    const horizontalScale = (nextWidth * 0.82) / Math.max(baseBounds.width, 1)
    const verticalScale = (nextHeight * 0.82) / Math.max(baseBounds.height, 1)
    const nextScale = Math.max(0.01, Math.min(horizontalScale, verticalScale) * defaultScaleMultiplier)

    const centerX = baseBounds.x + baseBounds.width / 2
    const centerY = baseBounds.y + baseBounds.height / 2
    const targetX = nextWidth * positionRatio.x
    const targetY = nextHeight * positionRatio.y

    /** 视口缩放：将截取区域拉伸到容器全尺寸 */
    const viewportScaleX = nextWidth / areaWidth
    const viewportScaleY = nextHeight / areaHeight

    model.scale.set(nextScale)
    model.position.set(
      targetX - centerX * nextScale,
      targetY - centerY * nextScale,
    )

    // 视口偏移 + 缩放：只显示 renderAreaRatio 指定的矩形区域
    app.stage.position.set(-areaLeft * viewportScaleX, -areaTop * viewportScaleY)
    app.stage.scale.set(viewportScaleX, viewportScaleY)
  }

  /** 按 tapGroups 轮播动作（点击模型空白区域时调用） */
  async function playNextMotion() {
    if (!model || options.tapGroups.length === 0) return null
    const key = 'tap'
    for (let i = 0; i < options.tapGroups.length; i++) {
      const group = options.tapGroups[getSequenceCursor(key, options.tapGroups.length)]
      try {
        const started = await model.motion(group, undefined, MotionPriority.FORCE)
        if (started) return group
      } catch (err) {
        // console.warn(`[Live2D] motion "${group}" failed`, err)
      }
    }
    return null
  }

  /** 按区域触发特定动作组 */
  async function playMotionForZone(zone: HitZone) {
    if (!model) return null
    const groups = options.zoneMotionGroups?.[zone]
    if (!groups || groups.length === 0) return playNextMotion()

    const key = `zone:${zone}`
    for (let i = 0; i < groups.length; i++) {
      const group = groups[getSequenceCursor(key, groups.length)]
      try {
        const started = await model.motion(group, undefined, MotionPriority.FORCE)
        if (started) return group
      } catch (err) {
        // console.warn(`[Live2D] zone motion "${group}" failed`, err)
      }
    }
    return null
  }

  /**
   * 将浏览器点击坐标转换为模型坐标系，判断命中头/身体区域。
   * 优先使用模型原生 hitTest，无 HitAreas 时退化为按 Y 轴比例近似。
   */
  function resolveZoneByPoint(clientX: number, clientY: number): HitZone | null {
    if (!model || !app || !baseBounds) return null

    const rect = app.canvas.getBoundingClientRect()
    if (rect.width <= 0 || rect.height <= 0) return null

    // 先尝试原生 hitTest
    const canvasPoint = new PIXI.Point(
      ((clientX - rect.left) / rect.width) * app.renderer.width,
      ((clientY - rect.top) / rect.height) * app.renderer.height,
    )
    const nativeHitAreas = model.hitTest(canvasPoint.x, canvasPoint.y)
    if (nativeHitAreas.length > 0) {
      const normalized = nativeHitAreas.map((n) => n.toLowerCase())
      if (normalized.some((n) => /head|face|hair|eye/.test(n))) return 'head'
      if (normalized.some((n) => /body|bust|arm|torso/.test(n))) return 'body'
    }

    // 兜底：按模型本体 Y 轴比例判断（上部 38% 为头）
    const modelPoint = model.toLocal(canvasPoint)
    const insideX = modelPoint.x >= baseBounds.x && modelPoint.x <= baseBounds.x + baseBounds.width
    const insideY = modelPoint.y >= baseBounds.y && modelPoint.y <= baseBounds.y + baseBounds.height
    if (!insideX || !insideY) return null

    const relativeY = (modelPoint.y - baseBounds.y) / Math.max(baseBounds.height, 1)
    return relativeY <= 0.38 ? 'head' : 'body'
  }

  /**
   * 清理本地引用，但保留模块级缓存的 Pixi App + 模型实例。
   * 真正销毁仅在整个页面卸载时做（由 disposeGlobal 触发）。
   */
  function dispose() {
    ready.value = false
    app = null
    model = null
    baseBounds = null
    options.container.replaceChildren()
  }

  /** 彻底销毁全局缓存的 Live2D 实例（页面卸载时调用） */
  function disposeGlobal() {
    for (const [, cache] of modelCache) {
      cache.model.destroy({ children: true })
      cache.app.destroy()
    }
    modelCache.clear()
  }

  return { ready, error, initialize, resize, dispose, disposeGlobal, playNextMotion, playMotionForZone, resolveZoneByPoint }
}
