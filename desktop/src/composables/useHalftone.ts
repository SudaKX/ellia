/**
 * # useHalftone — 图片点阵风格化渲染
 *
 * 将普通图片渲染为由规则排列的彩色圆点组成的点阵图。
 * 每个圆点大小与原始图片对应位置亮度成反比：
 * 越暗 → 圆点越大，越亮 → 圆点越小。
 *
 * ## 缓存策略
 *
 * 首次渲染时将结果绘制到一张"主画布"（分辨率 = 原图尺寸）并内存缓存。
 * 后续窗口缩放只需 `drawImage` 缩放主画布，不再重算所有圆点。
 * 图片切换时重新生成主画布。
 *
 * ## 使用方式
 *
 * ```ts
 * const halftone = useHalftone({ dotSpacing: 6, maxRadius: 5 })
 * await halftone.init(canvas)
 * await halftone.render('/path/to/image.webp')
 * halftone.destroy()
 * ```
 */

import { shallowRef } from 'vue'

export interface HalftoneOptions {
  /** 网格间距（CSS px），默认 3 */
  dotSpacing?: number
  /** 最暗区域圆点最大半径（CSS px），默认 2.5 */
  maxRadius?: number
  /** 最亮区域圆点最小半径（CSS px），默认 0.6 */
  minRadius?: number
}

const DEFAULTS: Required<HalftoneOptions> = {
  dotSpacing: 3,
  maxRadius: 2.5,
  minRadius: 0.6,
}

/** 从 document 解析 CSS 变量实际值 */
function resolveCssVar(name: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback
  const resolved = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return resolved || fallback
}

/** HiDPI 屏幕最大 DPR */
const MAX_DPR = 2

export function useHalftone(options?: HalftoneOptions) {
  const opts = { ...DEFAULTS, ...options }

  const canvasRef = shallowRef<HTMLCanvasElement | null>(null)

  let ctx: CanvasRenderingContext2D | null = null
  let cssWidth = 0
  let cssHeight = 0
  let currentUrl = ''
  let resizeObserver: ResizeObserver | null = null

  /** 主画布缓存：Map<imageUrl, HTMLCanvasElement>，所有渲染过的图都保留 */
  const cache = new Map<string, HTMLCanvasElement>()

  // ─── 主画布缓存 ──────────────────────────────────────

  function createMaster(w: number, h: number): { canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D } {
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    return { canvas, ctx: canvas.getContext('2d')! }
  }

  /**
   * 从原图生成点阵主画布，仅在图片切换时调用。
   * 在 masterCanvas（原图分辨率）上绘制所有圆点并缓存。
   */
  async function renderMaster(imageUrl: string): Promise<void> {
    // Step 1: 加载图片
    const image = new Image()
    image.crossOrigin = 'anonymous'
    image.src = imageUrl
    await image.decode()

    const imgW = image.naturalWidth
    const imgH = image.naturalHeight
    const { canvas: masterCanvas, ctx: masterCtx } = createMaster(imgW, imgH)

    // Step 2: 在原图分辨率空间采样
    const offscreen = document.createElement('canvas')
    offscreen.width = imgW
    offscreen.height = imgH
    const offCtx = offscreen.getContext('2d')!
    offCtx.drawImage(image, 0, 0)
    const imageData = offCtx.getImageData(0, 0, imgW, imgH)
    const pixels = imageData.data

    // Step 3: 清空主画布（透明），只靠格子 fillRect 覆盖角色区域
    masterCtx!.clearRect(0, 0, imgW, imgH)
    const baseColor = resolveCssVar('--canvas', '#0d0d10')

    // Step 4: 遍历网格 — 用量尺坐标（不缩放），因为 masterCanvas = 1:1 原图
    const { dotSpacing, maxRadius, minRadius } = opts
    const radiusRange = maxRadius - minRadius
    const cols = Math.floor(imgW / dotSpacing)
    const rows = Math.floor(imgH / dotSpacing)
    const cellW = Math.ceil(dotSpacing)
    const cellH = Math.ceil(dotSpacing)

    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const sx = Math.floor(col * dotSpacing + dotSpacing / 2)
        const sy = Math.floor(row * dotSpacing + dotSpacing / 2)
        const pixelIndex = (sy * imgW + sx) * 4

        const r = pixels[pixelIndex]
        const g = pixels[pixelIndex + 1]
        const b = pixels[pixelIndex + 2]
        const a = pixels[pixelIndex + 3]

        if (a < 128) continue

        const brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        const radius = minRadius + radiusRange * (1 - brightness)
        if (radius < 0.15) continue

        const cx = col * dotSpacing + dotSpacing / 2
        const cy = row * dotSpacing + dotSpacing / 2

        // 底层格子填底色
        masterCtx!.fillStyle = baseColor
        masterCtx!.fillRect(col * dotSpacing, row * dotSpacing, cellW, cellH)

        // 上层圆点
        masterCtx!.fillStyle = `rgb(${r},${g},${b})`
        masterCtx!.beginPath()
        masterCtx!.arc(cx, cy, radius, 0, Math.PI * 2)
        masterCtx!.fill()
      }
    }

    cache.set(imageUrl, masterCanvas)
  }

  /** 将主画布缩放到当前显示 canvas */
  function paintToDisplay(imageUrl: string): void {
    const masterCanvas = cache.get(imageUrl)
    if (!ctx || !masterCanvas || cssWidth <= 0 || cssHeight <= 0) return
    ctx.clearRect(0, 0, cssWidth, cssHeight)
    ctx.drawImage(masterCanvas, 0, 0, cssWidth, cssHeight)
  }

  // ─── DPR 感知的 canvas 尺寸调整 ─────────────────────────

  function resizeCanvas(): void {
    const canvas = canvasRef.value
    if (!canvas) return
    const parent = canvas.parentElement
    if (!parent) return

    const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR)
    const rect = parent.getBoundingClientRect()
    const w = Math.floor(rect.width)
    const h = Math.floor(rect.height)

    if (w <= 0 || h <= 0) return

    cssWidth = w
    cssHeight = h

    canvas.width = w * dpr
    canvas.height = h * dpr
    canvas.style.width = `${w}px`
    canvas.style.height = `${h}px`

    const newCtx = canvas.getContext('2d')!
    newCtx.scale(dpr, dpr)
    ctx = newCtx

    // 缩放主画布到新尺寸（极快，无需节流）
    paintToDisplay(currentUrl)
  }

  // ─── 公开 render ──────────────────────────────────────

  /**
   * 渲染图片为点阵。
   * 仅当图片 URL 变化时重新生成主画布，否则直接缩放到显示尺寸。
   */
  async function render(imageUrl: string): Promise<void> {
    currentUrl = imageUrl
    if (!cache.has(imageUrl)) {
      await renderMaster(imageUrl)
    }
    paintToDisplay(imageUrl)
  }

  // ─── 生命周期 ─────────────────────────────────────────

  async function init(canvas: HTMLCanvasElement): Promise<void> {
    canvasRef.value = canvas
    resizeCanvas()

    resizeObserver = new ResizeObserver(() => resizeCanvas())
    if (canvas.parentElement) {
      resizeObserver.observe(canvas.parentElement)
    }
  }

  function destroy(): void {
    resizeObserver?.disconnect()
    resizeObserver = null
    ctx = null
    canvasRef.value = null
    currentUrl = ''
    cache.clear()
  }

  return { canvasRef, init, render, destroy }
}
