/**
 * # useHalftone — 图片点阵风格化渲染
 *
 * 将普通图片渲染为由规则排列的彩色圆点组成的点阵图。
 * 每个圆点大小与原始图片对应位置亮度成反比：
 * 越暗 → 圆点越大，越亮 → 圆点越小。
 *
 * ## 渲染流程
 *
 * 1. `new Image()` 加载图片
 * 2. 在离屏 canvas 上以目标尺寸 + DPR 缩放绘制原图
 * 3. `getImageData()` 获取像素数据
 * 4. 遍历网格，每个格子采样中心像素 → 算亮度 → 画彩色圆点
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

/** HiDPI 屏幕最大 DPR */
const MAX_DPR = 2

export function useHalftone(options?: HalftoneOptions) {
  const opts = { ...DEFAULTS, ...options }

  const canvasRef = shallowRef<HTMLCanvasElement | null>(null)

  let ctx: CanvasRenderingContext2D | null = null
  let offscreen: HTMLCanvasElement | null = null
  let offCtx: CanvasRenderingContext2D | null = null
  let cssWidth = 0
  let cssHeight = 0
  let currentUrl = ''
  let resizeObserver: ResizeObserver | null = null
  let renderPending = false

  // ─── 离屏 Canvas ──────────────────────────────────────

  function ensureOffscreen(w: number, h: number): void {
    if (offscreen && offscreen.width === w && offscreen.height === h) return
    offscreen = document.createElement('canvas')
    offscreen.width = w
    offscreen.height = h
    offCtx = offscreen.getContext('2d')!
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

    // 尺寸变化后重新渲染当前图片
    if (currentUrl && !renderPending) {
      renderPending = true
      requestAnimationFrame(() => {
        renderPending = false
        render(currentUrl)
      })
    }
  }

  // ─── 核心渲染 ─────────────────────────────────────────

  /**
   * 加载图片并渲染为点阵。
   * 可多次调用以切换图片。
   */
  async function render(imageUrl: string): Promise<void> {
    currentUrl = imageUrl
    if (!ctx || cssWidth <= 0 || cssHeight <= 0) return

    // Step 1: 加载图片
    const image = new Image()
    image.crossOrigin = 'anonymous'
    image.src = imageUrl
    await image.decode()

    // Step 2: 离屏绘制原图（DPR 缩放以保持采样精度）
    const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR)
    const offW = cssWidth * dpr
    const offH = cssHeight * dpr
    ensureOffscreen(offW, offH)
    offCtx!.clearRect(0, 0, offW, offH)
    offCtx!.drawImage(image, 0, 0, offW, offH)

    // Step 3: 获取像素数据
    const imageData = offCtx!.getImageData(0, 0, offW, offH)
    const pixels = imageData.data

    // Step 4: 清空主 canvas（透明背景）
    ctx!.clearRect(0, 0, cssWidth, cssHeight)

    // Step 5: 遍历网格，绘制点阵
    const { dotSpacing, maxRadius, minRadius } = opts
    const radiusRange = maxRadius - minRadius

    // 按 DPR 缩放网格步长用于采样
    const sampleStep = dotSpacing * dpr
    const cols = Math.floor(offW / sampleStep)
    const rows = Math.floor(offH / sampleStep)

    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        // 离屏采样坐标（DPR 空间）
        const sx = Math.floor(col * sampleStep + sampleStep / 2)
        const sy = Math.floor(row * sampleStep + sampleStep / 2)
        const pixelIndex = (sy * offW + sx) * 4

        const r = pixels[pixelIndex]
        const g = pixels[pixelIndex + 1]
        const b = pixels[pixelIndex + 2]
        const a = pixels[pixelIndex + 3]

        // 透明像素不画
        if (a < 128) continue

        // 感知亮度（ITU-R BT.601）
        const brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        // 越暗 → 圆点越大
        const radius = minRadius + radiusRange * (1 - brightness)

        // 太小不画
        if (radius < 0.15) continue

        // 主 canvas 绘制坐标（CSS px 空间）
        const cx = col * dotSpacing + dotSpacing / 2
        const cy = row * dotSpacing + dotSpacing / 2

        ctx!.fillStyle = `rgb(${r},${g},${b})`
        ctx!.beginPath()
        ctx!.arc(cx, cy, radius, 0, Math.PI * 2)
        ctx!.fill()
      }
    }
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
    offscreen = null
    offCtx = null
    ctx = null
    canvasRef.value = null
    currentUrl = ''
  }

  return { canvasRef, init, render, destroy }
}
