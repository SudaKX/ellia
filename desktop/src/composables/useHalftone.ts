/**
 * # useHalftone — 图片点阵风格化渲染
 *
 * 将普通图片渲染为由规则排列的彩色圆点组成的点阵图。
 * 每个圆点大小与原始图片对应位置亮度成反比：
 * 越暗 → 圆点越大，越亮 → 圆点越小。
 *
 * ## 双层渲染结构
 *
 * ```
 * 底层（格子 fillRect）    — 固定浅色 #f0f0ed，仅覆盖角色不透明区域
 * 上层（点阵 circle）      — 原图像素颜色，半径由亮度决定
 * ```
 *
 * 透明区域（原图 alpha < 128）两层都不画，保持 canvas 透明。
 *
 * ## 缓存策略
 *
 * ```
 * 首次加载图片 A → renderMaster(A) → 存入 cache Map
 * 切换图片 B     → renderMaster(B) → 存入 cache Map
 * 切回图片 A     → cache.has(A) ✓ → 直接 paintToDisplay(A)
 * 窗口缩放       → paintToDisplay(currentUrl)  — 仅一次 drawImage，不重算
 * ```
 *
 * 主画布分辨率 = 裁切区域尺寸（未裁切时 = 原图 naturalWidth × naturalHeight），
 * 保证采样精度，缩放时由浏览器原生 drawImage 处理。
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

/** 裁切区域：相对原图的比例坐标（0~1），换算像素时四舍五入并钳制在图内 */
export interface HalftoneCrop {
  /** 裁切区左上角 X 比例 */
  x: number
  /** 裁切区左上角 Y 比例 */
  y: number
  /** 裁切区宽度比例 */
  width: number
  /** 裁切区高度比例 */
  height: number
}

export interface HalftoneOptions {
  /** 网格间距（CSS px），默认 3 */
  dotSpacing?: number
  /** 最暗区域圆点最大半径（CSS px），默认 2.5 */
  maxRadius?: number
  /** 最亮区域圆点最小半径（CSS px），默认 0.6 */
  minRadius?: number
  /** 可选裁切区域（相对原图比例），默认全图 */
  crop?: HalftoneCrop
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
   * 从原图生成点阵主画布，仅在图片首次加载时调用。
   *
   * ## 算法
   *
   * 1. 加载图片 → 取 naturalWidth × naturalHeight
   * 2. 创建同尺寸离屏 canvas → drawImage 原图 → getImageData
   * 3. 按 dotSpacing 步长遍历原图每个格子：
   *    - 采样格子中心像素 RGB
   *    - 算感知亮度 = (0.299R + 0.587G + 0.114B) / 255  （ITU-R BT.601）
   *    - 圆点半径 = minRadius + (maxRadius - minRadius) × (1 - brightness)
   *      亮度越高 → 1-brightness 越小 → 圆点越小
   *      亮度越低 → 1-brightness 越大 → 圆点越大
   *    - 画 fillRect 底色 + 画彩色 circle
   * 4. 存入 cache.set(imageUrl, masterCanvas)
   *
   * @param imageUrl 图片 URL，同时也是缓存 key
   */
  async function renderMaster(imageUrl: string): Promise<void> {
    // Step 1: 加载图片（decode 失败时兜底到 onload，仍失败则抛出，由 render 调用方决定如何降级）
    const image = new Image()
    image.crossOrigin = 'anonymous'
    image.src = imageUrl

    try {
      await image.decode()
    } catch {
      // 部分环境/图片 decode 不可用或加载失败 → 回退到 onload 等待
      await new Promise<void>((resolve, reject) => {
        image.onload = () => resolve()
        image.onerror = () => reject(new Error(`Halftone image load failed: ${imageUrl}`))
        // 已缓存图片可能不触发 onload 回调，检查尺寸兜底
        if (image.complete && image.naturalWidth > 0) resolve()
      })
    }

    const imgW = image.naturalWidth
    const imgH = image.naturalHeight
    // 可选裁切：相对原图比例（0~1），默认全图；像素坐标四舍五入并钳制在图内
    const crop = opts.crop ?? { x: 0, y: 0, width: 1, height: 1 }
    const cropX = Math.max(0, Math.round(crop.x * imgW))
    const cropY = Math.max(0, Math.round(crop.y * imgH))
    const cropW = Math.max(1, Math.min(imgW - cropX, Math.round(crop.width * imgW)))
    const cropH = Math.max(1, Math.min(imgH - cropY, Math.round(crop.height * imgH)))
    const { canvas: masterCanvas, ctx: masterCtx } = createMaster(cropW, cropH)

    // Step 2: 在原图分辨率空间采样（仅裁切区域，masterCanvas 尺寸 = 裁切区域）
    const offscreen = document.createElement('canvas')
    offscreen.width = imgW
    offscreen.height = imgH
    const offCtx = offscreen.getContext('2d')!
    offCtx.drawImage(image, 0, 0)
    const imageData = offCtx.getImageData(cropX, cropY, cropW, cropH)
    const pixels = imageData.data

    // Step 3: 清空主画布（透明），只靠格子 fillRect 覆盖角色区域
    masterCtx!.clearRect(0, 0, cropW, cropH)
    const baseColor = '#f0f0ed'  // 浅色背景，固定不随主题切换

    // Step 4: 遍历网格 — 用量尺坐标（不缩放），因为 masterCanvas = 1:1 裁切区域
    //
    // 网格划分（相对裁切区域）：
    //   cols = floor(cropW / dotSpacing)
    //   rows = floor(cropH / dotSpacing)
    //
    // 采样坐标系（原图像素空间，裁切区左上角为 cropX/cropY 偏移）：
    //   sx = cropX + col * dotSpacing + dotSpacing / 2  格子中心 X
    //   sy = cropY + row * dotSpacing + dotSpacing / 2  格子中心 Y
    //   pixelIndex = ((sy - cropY) * cropW + (sx - cropX)) * 4   RGBA 起始索引
    //
    // 绘制坐标系（masterCanvas 局部坐标，1:1）：
    //   cx = col * dotSpacing + dotSpacing / 2
    //   cy = row * dotSpacing + dotSpacing / 2
    const { dotSpacing, maxRadius, minRadius } = opts
    const radiusRange = maxRadius - minRadius
    const cols = Math.floor(cropW / dotSpacing)
    const rows = Math.floor(cropH / dotSpacing)
    const cellW = Math.ceil(dotSpacing)
    const cellH = Math.ceil(dotSpacing)

    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        // 采样：在裁切区域（原图分辨率空间偏移 cropX/cropY）取格子中心像素
        const sx = cropX + Math.floor(col * dotSpacing + dotSpacing / 2)
        const sy = cropY + Math.floor(row * dotSpacing + dotSpacing / 2)
        const pixelIndex = ((sy - cropY) * cropW + (sx - cropX)) * 4   // RGBA 各 1 字节

        const r = pixels[pixelIndex]       // Red   0-255
        const g = pixels[pixelIndex + 1]   // Green 0-255
        const b = pixels[pixelIndex + 2]   // Blue  0-255
        const a = pixels[pixelIndex + 3]   // Alpha 0-255

        // 透明区域（webp 立绘背景）跳过，不画任何东西
        if (a < 128) continue

        // 感知亮度 0..1，人眼对绿色最敏感（ITU-R BT.601）
        const brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        // 圆点半径 = 暗→大，亮→小
        const radius = minRadius + radiusRange * (1 - brightness)
        if (radius < 0.15) continue   // 太小不画，节省绘制开销

        const cx = col * dotSpacing + dotSpacing / 2
        const cy = row * dotSpacing + dotSpacing / 2

        // 底层：浅色格子 fillRect（ceil 消除亚像素间隙）
        masterCtx!.fillStyle = baseColor
        masterCtx!.fillRect(col * dotSpacing, row * dotSpacing, cellW, cellH)

        // 上层：彩色圆点，颜色直接取自原图像素
        masterCtx!.fillStyle = `rgb(${r},${g},${b})`
        masterCtx!.beginPath()
        masterCtx!.arc(cx, cy, radius, 0, Math.PI * 2)
        masterCtx!.fill()
      }
    }

    cache.set(imageUrl, masterCanvas)
  }

  /**
   * 将缓存的 masterCanvas 等比缩放到当前显示 canvas（contain 模式）。
   *
   * 这是热点路径——每次 resizeObserver 触发都会调用。
   * 仅一次 ctx.drawImage，由浏览器 GPU 加速缩放，无任何遍历。
   *
   * ## 等比 contain
   *
   * 保持原图宽高比缩放并居中绘制，多余区域保持透明：
   * 窗口被拉伸到任意宽高比时，点阵图都不会变形。
   * （原图 1:1、显示区域 1:1 时等同于铺满，行为与旧版一致。）
   *
   * @param imageUrl 要显示的图片 URL，用于从 cache 取对应的 masterCanvas
   */
  function paintToDisplay(imageUrl: string): void {
    const masterCanvas = cache.get(imageUrl)
    if (!ctx || !masterCanvas || cssWidth <= 0 || cssHeight <= 0) return
    ctx.clearRect(0, 0, cssWidth, cssHeight)

    // contain：按原图比例缩放，取能完整放入显示区域的尺寸，居中
    const ratio = masterCanvas.width / masterCanvas.height
    let drawWidth = cssWidth
    let drawHeight = drawWidth / ratio
    if (drawHeight > cssHeight) {
      drawHeight = cssHeight
      drawWidth = drawHeight * ratio
    }
    const offsetX = (cssWidth - drawWidth) / 2
    const offsetY = (cssHeight - drawHeight) / 2
    ctx.drawImage(masterCanvas, offsetX, offsetY, drawWidth, drawHeight)
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
   * 渲染图片为点阵（公开 API，由 AiAssistant.vue 调用）。
   *
   * ## 路径
   *
   * ```
   * cache.has(url)?
   *   ├─ YES → paintToDisplay(url)              // 已缓存，直接缩放
   *   └─ NO  → renderMaster(url)                // 首次，生成主画布
   *            └─ paintToDisplay(url)            // 缩放显示
   * ```
   *
   * 调用时机：
   * - AiAssistant.vue `onMounted`：首次渲染
   * - AiAssistant.vue `watch(currentImage)`：用户点击切换图片
   *
   * @param imageUrl 图片 URL
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
