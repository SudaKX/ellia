import { ref, shallowRef } from 'vue'

/**
 * 01 红色故障闪烁效果配置选项。
 * 所有选项均为可选，未指定时使用默认值。
 */
export interface MatrixRainOptions {
  /** 闪烁字符集，默认 ['0', '1'] */
  characters: string[]
  /** 字符颜色，默认 '#e34d55'（--signal-red 警示红） */
  color: string
  /** 字体大小（CSS px），默认 18 */
  fontSize: number
  /** 激活比例 0-1，默认 0.35 */
  density: number
  /** 最短闪烁周期（帧数），默认 2 */
  minFlickerFrames: number
  /** 最长闪烁周期（帧数），默认 25 */
  maxFlickerFrames: number
  /** 目标帧率，默认 24 */
  fps: number
  /** 故障爆发概率（每帧），默认 0.003 */
  burstProbability: number
  /** Canvas 背景色，默认 'rgba(13, 13, 16, 0.12)'（--canvas + 轻度叠加） */
  backgroundColor: string
}

const DEFAULTS: MatrixRainOptions = {
  characters: ['0', '1'],
  /** 使用 CSS 变量以支持主题切换，fallback 为警示红 */
  color: 'var(--matrix-rain-color, #e34d55)',
  fontSize: 18,
  density: 0.35,
  minFlickerFrames: 2,
  maxFlickerFrames: 25,
  fps: 24,
  burstProbability: 0.003,
  /** Canvas 覆盖层背景色，跟随主题 */
  backgroundColor: 'var(--matrix-rain-bg, rgba(13, 13, 16, 0.12))',
}

/** 等宽字体族 */
const FONT_FAMILY = '"IBM Plex Mono", "Courier New", Consolas, "Liberation Mono", monospace'
/** 等宽字符宽度 ≈ fontSize × 0.6 */
const CHAR_WIDTH_RATIO = 0.6
/** HiDPI 屏幕最大 DPR */
const MAX_DPR = 2

/**
 * 将 CSS 变量字符串解析为实际颜色值。
 * Canvas API 不支持 var()，需要用 getComputedStyle 手动解析。
 *
 * @example
 * resolveCssVar('var(--matrix-rain-color, #e34d55)') → '#e34d55' (根据主题)
 */
function resolveCssVar(value: string): string {
  const match = value.match(/var\((--[\w-]+),\s*(.+)\)/)
  if (!match) return value
  const varName = match[1]
  const fallback = match[2].trim()
  if (typeof document === 'undefined') return fallback
  const resolved = getComputedStyle(document.documentElement).getPropertyValue(varName).trim()
  return resolved || fallback
}

// ─── 内部类型 ──────────────────────────────────────────────

interface FlickerCell {
  /** 字符水平中心位置（CSS px） */
  x: number
  /** 字符垂直基线（CSS px） */
  y: number
  /** 当前显示的字符 */
  char: string
  /** 当前是否可见 */
  visible: boolean
  /** 距离下次翻转的剩余帧数 */
  counter: number
  /** 本周期总帧数（counter 归零后重新随机） */
  maxFrames: number
  /** 该 cell 的基础透明度 0.4 ~ 1.0 */
  alpha: number
}

// ─── 工具函数 ──────────────────────────────────────────────

function randomInt(min: number, max: number): number {
  return min + Math.floor(Math.random() * (max - min + 1))
}

// ─── Composable ────────────────────────────────────────────

export function useMatrixRain(options?: Partial<MatrixRainOptions>) {
  const opts = { ...DEFAULTS, ...options }
  // Canvas API 不支持 var()，需在运行时解析 CSS 变量为实际颜色值
  opts.color = resolveCssVar(opts.color)
  opts.backgroundColor = resolveCssVar(opts.backgroundColor)

  const canvasRef = shallowRef<HTMLCanvasElement | null>(null)
  const isRunning = ref(false)

  let animationId: number | null = null
  let ctx: CanvasRenderingContext2D | null = null
  let cssWidth = 0
  let cssHeight = 0
  let cells: FlickerCell[] = []
  let resizeObserver: ResizeObserver | null = null
  let themeObserver: MutationObserver | null = null
  let lastFrameTime = 0
  let frameInterval = 0

  function randomChar(): string {
    return opts.characters[Math.floor(Math.random() * opts.characters.length)]
  }

  /** 根据 canvas 尺寸重建闪烁网格 */
  function createGrid(): void {
    const charWidth = opts.fontSize * CHAR_WIDTH_RATIO
    const totalCols = Math.max(1, Math.floor(cssWidth / charWidth))
    const totalRows = Math.max(1, Math.floor(cssHeight / opts.fontSize))
    cells = []

    for (let col = 0; col < totalCols; col++) {
      for (let row = 0; row < totalRows; row++) {
        // 按 density 概率跳过非激活格
        if (Math.random() > opts.density) continue

        const maxFrames = randomInt(opts.minFlickerFrames, opts.maxFlickerFrames)

        cells.push({
          x: Math.round(col * charWidth + charWidth / 2),
          y: Math.round(row * opts.fontSize + opts.fontSize * 0.85),
          char: randomChar(),
          visible: Math.random() > 0.5,
          counter: randomInt(0, maxFrames),
          maxFrames,
          alpha: 0.4 + Math.random() * 0.6, // 0.4 ~ 1.0
        })
      }
    }
  }

  /** DPR 感知的 canvas 尺寸调整 */
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

    createGrid()
  }

  /** 随机点亮一批 cell，制造故障爆发效果 */
  function triggerBurst(): void {
    // 随机选取 10% ~ 30% 的 cell 同时点亮
    const burstCount = Math.floor(cells.length * (0.1 + Math.random() * 0.2))
    for (let i = 0; i < burstCount; i++) {
      const idx = Math.floor(Math.random() * cells.length)
      const cell = cells[idx]
      cell.visible = true
      cell.char = randomChar()
      cell.maxFrames = randomInt(opts.minFlickerFrames, Math.max(opts.minFlickerFrames + 3, 6))
      cell.counter = randomInt(0, cell.maxFrames)
    }
  }

  /** 单帧绘制 */
  function render(): void {
    if (!ctx || cssWidth <= 0 || cssHeight <= 0) return

    // Step 1: 半透明暗色覆盖，持续压低背景
    ctx.fillStyle = opts.backgroundColor
    ctx.fillRect(0, 0, cssWidth, cssHeight)

    // Step 2: 设置字体
    ctx.font = `${opts.fontSize}px ${FONT_FAMILY}`
    ctx.textBaseline = 'top'
    ctx.textAlign = 'center'

    // Step 3: 遍历所有 cell —— 翻转 & 绘制
    for (const cell of cells) {
      cell.counter--

      if (cell.counter <= 0) {
        // 翻转可见性
        cell.visible = !cell.visible
        // 重新随机周期
        cell.maxFrames = randomInt(opts.minFlickerFrames, opts.maxFlickerFrames)
        cell.counter = cell.maxFrames
        // 可见时换一个新字符
        if (cell.visible) {
          cell.char = randomChar()
        }
      }

      // 仅绘制可见字符
      if (cell.visible) {
        ctx!.globalAlpha = cell.alpha
        ctx!.fillStyle = opts.color
        ctx!.fillText(cell.char, cell.x, cell.y)
      }
    }
    ctx!.globalAlpha = 1

    // Step 4: 故障爆发概率
    if (Math.random() < opts.burstProbability) {
      triggerBurst()
    }
  }

  // ─── RAF 动画循环 ──────────────────────────────────────

  function animationLoop(timestamp: number): void {
    if (!isRunning.value) return

    if (frameInterval <= 0 || timestamp - lastFrameTime >= frameInterval) {
      lastFrameTime = timestamp
      render()
    }

    animationId = requestAnimationFrame(animationLoop)
  }

  function startLoop(): void {
    if (isRunning.value) return
    isRunning.value = true
    lastFrameTime = 0
    animationId = requestAnimationFrame(animationLoop)
  }

  function stopLoop(): void {
    isRunning.value = false
    if (animationId !== null) {
      cancelAnimationFrame(animationId)
      animationId = null
    }
  }

  // ─── 公开 API ──────────────────────────────────────────

  async function init(canvas: HTMLCanvasElement): Promise<void> {
    canvasRef.value = canvas
    frameInterval = opts.fps > 0 ? 1000 / opts.fps : 0

    resizeCanvas()

    resizeObserver = new ResizeObserver(() => resizeCanvas())
    if (canvas.parentElement) {
      resizeObserver.observe(canvas.parentElement)
    }

    // 监听主题切换，重新解析 CSS 变量并重建网格
    themeObserver = new MutationObserver(() => {
      opts.color = resolveCssVar(DEFAULTS.color)
      opts.backgroundColor = resolveCssVar(DEFAULTS.backgroundColor)
      createGrid()
    })
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

    await document.fonts.ready

    startLoop()
  }

  function destroy(): void {
    stopLoop()
    resizeObserver?.disconnect()
    resizeObserver = null
    themeObserver?.disconnect()
    themeObserver = null
    canvasRef.value = null
    ctx = null
    cells = []
  }

  function start(): void {
    startLoop()
  }

  function stop(): void {
    stopLoop()
  }

  function updateOptions(newOpts: Partial<MatrixRainOptions>): void {
    Object.assign(opts, newOpts)
    frameInterval = opts.fps > 0 ? 1000 / opts.fps : 0
    createGrid()
  }

  return {
    isRunning,
    init,
    destroy,
    start,
    stop,
    updateOptions,
  }
}
