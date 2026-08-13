import {
  prepareWithSegments,
  layoutNextLineRange,
  materializeLineRange,
  clearCache,
} from '@chenglou/pretext'
import type { PreparedTextWithSegments, LayoutCursor } from '@chenglou/pretext'
import { ref, shallowRef } from 'vue'

export interface AsciiFlowOptions {
  text: string
  font: string
  lineHeight: number
  obstacleRadius: number
  loopText: boolean
}

interface ObstacleSpan {
  left: number
  right: number
}

/**
 * Composable for the variable typographic ASCII flow effect.
 * Uses @chenglou/pretext to layout text around a movable obstacle on a canvas.
 */
export function useAsciiFlow(initialOptions: AsciiFlowOptions) {
  const options = { ...initialOptions }
  const canvasRef = shallowRef<HTMLCanvasElement | null>(null)

  const obstacleX = ref(0)
  const obstacleY = ref(0)
  const obstacleRadius = ref(options.obstacleRadius)

  let prepared: PreparedTextWithSegments | null = null
  let animationId: number | null = null
  let ctx: CanvasRenderingContext2D | null = null
  let cssWidth = 0
  let cssHeight = 0
  let dpr = 1

  // --- Interaction state ---
  const isDragging = ref(false)
  const isHovering = ref(false)

  // --- Prepare text ---
  async function prepareText(): Promise<void> {
    await document.fonts.ready
    clearCache()
    prepared = prepareWithSegments(options.text, options.font)
  }

  // --- Obstacle span calculation ---
  function getObstacleSpans(y: number): ObstacleSpan[] {
    const ox = obstacleX.value
    const oy = obstacleY.value
    const r = obstacleRadius.value
    const padX = 12
    const W = cssWidth

    const dy = y - oy
    if (Math.abs(dy) >= r) {
      return [{ left: padX, right: W - padX }]
    }

    const dx = Math.sqrt(Math.max(0, r * r - dy * dy))
    const leftEdge = ox - dx
    const rightEdge = ox + dx

    const spans: ObstacleSpan[] = []
    if (leftEdge > padX + 4) {
      spans.push({ left: padX, right: leftEdge })
    }
    if (rightEdge < W - padX - 4) {
      spans.push({ left: rightEdge, right: W - padX })
    }
    return spans
  }

  // --- Render frame ---
  function render() {
    const canvas = canvasRef.value
    if (!canvas || !prepared || !ctx) return

    const W = cssWidth
    const H = cssHeight
    const padY = 10
    const lh = options.lineHeight

    if (W <= 0 || H <= 0) return

    // Background
    ctx.fillStyle = '#0d0d0f'
    ctx.fillRect(0, 0, W, H)

    // Subtle grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)'
    ctx.lineWidth = 1
    const gridSize = 48
    for (let gx = gridSize; gx < W; gx += gridSize) {
      ctx.beginPath()
      ctx.moveTo(gx, 0)
      ctx.lineTo(gx, H)
      ctx.stroke()
    }
    for (let gy = gridSize; gy < H; gy += gridSize) {
      ctx.beginPath()
      ctx.moveTo(0, gy)
      ctx.lineTo(W, gy)
      ctx.stroke()
    }

    // Layout text around obstacle
    ctx.font = options.font
    ctx.textBaseline = 'alphabetic'

    let cursor: LayoutCursor = { segmentIndex: 0, graphemeIndex: 0 }
    let y = padY
    let textExhausted = false

    while (y < H - padY) {
      const spans = getObstacleSpans(y)

      for (const span of spans) {
        if (textExhausted) break
        const availableWidth = span.right - span.left
        if (availableWidth < 8) continue

        const range = layoutNextLineRange(prepared!, cursor, availableWidth)
        if (!range) {
          if (options.loopText) {
            cursor = { segmentIndex: 0, graphemeIndex: 0 }
            const retryRange = layoutNextLineRange(prepared!, cursor, availableWidth)
            if (!retryRange) {
              textExhausted = true
              break
            }
            const line = materializeLineRange(prepared!, retryRange)
            ctx.fillStyle = '#b0b8c0'
            ctx.fillText(line.text, span.left, y + lh - 4)
            cursor = retryRange.end
          } else {
            textExhausted = true
            break
          }
        } else {
          const line = materializeLineRange(prepared!, range)
          ctx.fillStyle = '#b0b8c0'
          ctx.fillText(line.text, span.left, y + lh - 4)
          cursor = range.end
        }
      }

      y += lh
    }

    // --- Draw obstacle ---
    const ox = obstacleX.value
    const oy = obstacleY.value
    const r = obstacleRadius.value

    // Glow
    const glow = ctx.createRadialGradient(ox, oy, r * 0.7, ox, oy, r * 1.5)
    glow.addColorStop(0, 'rgba(220, 50, 50, 0.12)')
    glow.addColorStop(0.5, 'rgba(220, 50, 50, 0.04)')
    glow.addColorStop(1, 'rgba(220, 50, 50, 0)')
    ctx.fillStyle = glow
    ctx.beginPath()
    ctx.arc(ox, oy, r * 1.5, 0, Math.PI * 2)
    ctx.fill()

    // Void fill
    ctx.fillStyle = 'rgba(13, 13, 15, 0.85)'
    ctx.beginPath()
    ctx.arc(ox, oy, r, 0, Math.PI * 2)
    ctx.fill()

    // Border ring
    ctx.strokeStyle = isHovering.value
      ? 'rgba(255, 80, 80, 0.7)'
      : 'rgba(200, 50, 50, 0.35)'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.arc(ox, oy, r, 0, Math.PI * 2)
    ctx.stroke()

    // Inner ring
    ctx.strokeStyle = 'rgba(255, 60, 60, 0.15)'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.arc(ox, oy, r * 0.85, 0, Math.PI * 2)
    ctx.stroke()

    // ASCII label inside obstacle
    const labelFontSize = Math.max(10, Math.floor(r * 0.28))
    ctx.font = `${labelFontSize}px "Courier New", monospace`
    ctx.fillStyle = 'rgba(200, 50, 50, 0.5)'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'

    const asciiLines = ['▓▓▓▓▓▓▓', '▓ ◇ VOID ◇ ▓', '▓▓▓▓▓▓▓']
    const gap = labelFontSize + 2
    const totalH = asciiLines.length * gap
    const startY = oy - totalH / 2
    for (let i = 0; i < asciiLines.length; i++) {
      ctx.fillText(asciiLines[i], ox, startY + i * gap + labelFontSize / 2)
    }
    ctx.textAlign = 'start'
    ctx.textBaseline = 'alphabetic'
  }

  // --- Animation loop ---
  function startLoop() {
    if (animationId !== null) return
    function loop() {
      render()
      animationId = requestAnimationFrame(loop)
    }
    loop()
  }

  function stopLoop() {
    if (animationId !== null) {
      cancelAnimationFrame(animationId)
      animationId = null
    }
  }

  // --- Canvas sizing with DPR ---
  function resizeCanvas() {
    const canvas = canvasRef.value
    if (!canvas) return
    const parent = canvas.parentElement
    if (!parent) return

    dpr = window.devicePixelRatio || 1
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

    // Re-create context with DPR scale
    const newCtx = canvas.getContext('2d')!
    newCtx.scale(dpr, dpr)
    ctx = newCtx

    // Set initial obstacle position if not yet positioned
    if (obstacleX.value === 0 && obstacleY.value === 0) {
      obstacleX.value = w * 0.65
      obstacleY.value = h * 0.45
    }
  }

  let resizeObserver: ResizeObserver | null = null

  // --- Mouse / touch coordinate helper ---
  function canvasPos(event: MouseEvent): { mx: number; my: number } {
    const canvas = canvasRef.value!
    const rect = canvas.getBoundingClientRect()
    return {
      mx: event.clientX - rect.left,
      my: event.clientY - rect.top,
    }
  }

  function distToObstacle(mx: number, my: number): number {
    const dx = mx - obstacleX.value
    const dy = my - obstacleY.value
    return Math.sqrt(dx * dx + dy * dy)
  }

  // --- Mouse handlers ---
  function onCanvasMouseDown(event: MouseEvent) {
    const { mx, my } = canvasPos(event)
    if (distToObstacle(mx, my) < obstacleRadius.value + 8) {
      isDragging.value = true
      event.preventDefault()
      window.addEventListener('mousemove', onWindowDragMove)
      window.addEventListener('mouseup', onWindowDragUp)
    }
  }

  function onCanvasMouseMove(event: MouseEvent) {
    const { mx, my } = canvasPos(event)
    const near = distToObstacle(mx, my) < obstacleRadius.value + 8
    isHovering.value = near

    const canvas = canvasRef.value!
    if (isDragging.value) {
      canvas.style.cursor = 'grabbing'
    } else {
      canvas.style.cursor = near ? 'grab' : 'default'
    }
  }

  function onWindowDragMove(event: MouseEvent) {
    if (!isDragging.value) return
    const { mx, my } = canvasPos(event)
    const r = obstacleRadius.value
    obstacleX.value = Math.max(r, Math.min(mx, cssWidth - r))
    obstacleY.value = Math.max(r, Math.min(my, cssHeight - r))
  }

  function onWindowDragUp() {
    isDragging.value = false
    window.removeEventListener('mousemove', onWindowDragMove)
    window.removeEventListener('mouseup', onWindowDragUp)
    const canvas = canvasRef.value
    if (canvas) {
      canvas.style.cursor = isHovering.value ? 'grab' : 'default'
    }
  }

  function onCanvasWheel(event: WheelEvent) {
    const { mx, my } = canvasPos(event)
    if (distToObstacle(mx, my) < obstacleRadius.value + 20) {
      event.preventDefault()
      const delta = event.deltaY > 0 ? 5 : -5
      obstacleRadius.value = Math.max(30, Math.min(200, obstacleRadius.value + delta))
    }
  }

  // --- Public API ---
  async function init(canvas: HTMLCanvasElement) {
    canvasRef.value = canvas
    resizeCanvas()

    resizeObserver = new ResizeObserver(() => {
      resizeCanvas()
    })
    if (canvas.parentElement) {
      resizeObserver.observe(canvas.parentElement)
    }

    canvas.addEventListener('mousedown', onCanvasMouseDown)
    canvas.addEventListener('mousemove', onCanvasMouseMove)
    canvas.addEventListener('wheel', onCanvasWheel, { passive: false })

    await prepareText()
    startLoop()
  }

  function destroy() {
    stopLoop()
    resizeObserver?.disconnect()
    resizeObserver = null

    const canvas = canvasRef.value
    if (canvas) {
      canvas.removeEventListener('mousedown', onCanvasMouseDown)
      canvas.removeEventListener('mousemove', onCanvasMouseMove)
      canvas.removeEventListener('wheel', onCanvasWheel)
    }
    window.removeEventListener('mousemove', onWindowDragMove)
    window.removeEventListener('mouseup', onWindowDragUp)

    canvasRef.value = null
    prepared = null
    ctx = null
  }

  async function updateText(text: string) {
    options.text = text
    prepared = null
    await prepareText()
  }

  return {
    obstacleX,
    obstacleY,
    obstacleRadius,
    isDragging,
    isHovering,
    init,
    destroy,
    updateText,
  }
}
