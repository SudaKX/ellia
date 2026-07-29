<script setup lang="ts">
/**
 * # 窗口框架组件
 *
 * FakeOS 窗口的视觉外壳，提供标题栏、拖拽、缩放、最小化、关闭等功能。
 *
 * ## 窗口状态
 *
 * - **entering**：初始挂载时的入场缩放动画（scale 0.4 → 1.0）
 * - **closing**：关闭动画（scale 1.0 → 0.4 + opacity → 0），transitionend 后 emit('close')
 * - **minimized**：最小化（scaleY(0) + opacity: 0）
 * - **dragging**：拖拽中（mousedown → mousemove → mouseup）
 * - **resizing**：缩放中（右下角 handle mousedown → mousemove → mouseup）
 * - **active**：聚焦状态（边框变红、阴影加深）
 * - **modal**：模态窗口（role="dialog", aria-modal="true"）
 *
 * ## 滤镜系统
 *
 * 通过 `filterIds` prop 接收 FilterType → SVG filter ID 的映射。
 * computed `filterValue` 遍历 `window.filters`，拼接成 CSS `url(#glitch-xxx)`。
 *
 * ## 生命周期
 *
 * ```
 * onMounted → getBoundingClientRect()（强制回流）
 *   → requestAnimationFrame → isEntering = false（入场动画完成）
 * onBeforeUnmount → cancelAnimationFrame（清理）
 * ```
 *
 * ## 拖拽与缩放
 *
 * 拖拽：titlebar mousedown → document mousemove → 更新 x/y → mouseup 回写 window
 * 缩放：resize-handle mousedown → document mousemove → 更新 width/height → mouseup 回写 window
 * 最小宽度 260px，最小高度 160px
 *
 * ## 与 darksky 分支区别
 *
 * 本分支支持 modal 模式（独立的 role/aria 属性）、
 * 窗口滤镜渲染、`controls.close`/`controls.minimize` 开关、
 * 以及 hideTitlebar 模式（隐藏原生标题栏，内容组件自行定义外观）。
 */

import { Minus, X } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { FilterType } from '@/registries/filters'
import type { WindowInstance } from '@/types/desktop'

const props = defineProps<{
  window: WindowInstance
  isActive: boolean
  filterIds: Partial<Record<FilterType, string>>
  /**
   * 隐藏原生标题栏。
   * 为 true 时不渲染标题栏，内容组件填满整个窗口区域。
   * 适用于需要完全自定义标题栏/控件外观的场景（如 AI 助手浮窗）。
   *
   * **默认值 undefined（falsy）——不传该 prop 的现有窗口不受任何影响。**
   *
   * 注意：隐藏标题栏后，拖拽功能也同时消失。
   * 如需拖拽，由内容组件自行实现。
   */
  hideTitlebar?: boolean
  /**
   * 等比缩放比例（宽/高）。
   * 提供后，缩放时 width = height * aspectRatio。
   * undefined 时自由缩放（默认行为，现有窗口不受影响）。
   * 例如：正方形图片设 1，16:9 宽屏设 16/9。
   *
   * 注意：此属性约束整个窗口（含标题栏）的宽高比。
   * 如需约束内容区域（不含标题栏），使用 bodyAspectRatio。
   */
  aspectRatio?: number
  /**
   * 内容区域等比缩放比例（宽/高），不含标题栏与边框。
   * 例如设 1 时，body 区域始终保持正方形，标题栏高度另算。
   * 与 aspectRatio 互斥，同时设置时 aspectRatio 生效。
   */
  bodyAspectRatio?: number
  /**
   * 最小宽度。覆盖模块默认 MIN_WIDTH(260)。
   * 不传时使用默认值，现有窗口不受影响。
   */
  minWidth?: number
  /**
   * 最小高度。覆盖模块默认 MIN_HEIGHT(160)。
   * 不传时使用默认值，现有窗口不受影响。
   */
  minHeight?: number
  /**
   * 最大宽度。undefined 时不设上限。
   */
  maxWidth?: number
  /**
   * 最大高度。undefined 时不设上限。
   */
  maxHeight?: number
  /**
   * 动态标题文本。提供后直接显示（不走 i18n），覆盖 titleKey。
   * 不传时使用 t(window.titleKey) 的国际化文本。
   * 适用于标题栏需要动态变化内容的场景（如 AI 聊天消息）。
   */
  title?: string
  /**
   * 自定义关闭按钮行为。
   * 提供后，标题栏 X 按钮显示但调用此函数而非触发关闭动画。
   * 适用于"点击关闭 → 弹出错误而不是真正关闭"等场景。
   * 不提供时走默认关闭流程，现有窗口不受影响。
   */
  closeAction?: () => void
  /** 窗口背景半透明（内容保持完全不透明）。 */
  translucent?: boolean
  /**
   * 跳过首次挂载时的入场动画。
   * 适用于页面加载时已经处于显示态的窗口（如 AI 助手），
   * 它们无需播放入场动画（因为没有经历"打开"这个过程）。
   * 不传时默认播放入场动画，现有窗口不受影响。
   */
  skipEnterAnimation?: boolean
}>()

const { t } = useI18n({ useScope: 'global' })

const emit = defineEmits<{
  close: []
  focus: []
  minimize: []
}>()

const MIN_WIDTH = 260
const MIN_HEIGHT = 160

/** 钳制值到 [min, max] 区间 */
function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

/**
 * 当前窗口有效的最小/最大尺寸。
 * 优先用 prop 值，不传时 fallback 到模块常量（min）或 Infinity（max）。
 */
const effectiveMinWidth = computed(() => props.minWidth ?? MIN_WIDTH)
const effectiveMinHeight = computed(() => props.minHeight ?? MIN_HEIGHT)
const effectiveMaxWidth = computed(() => props.maxWidth ?? Infinity)
const effectiveMaxHeight = computed(() => props.maxHeight ?? Infinity)

const x = ref(props.window.x)
const y = ref(props.window.y)
const width = ref(props.window.width)
const height = ref(props.window.height)

// 同步外部位置变化（如漂移）到本地 ref，拖拽期间跳过
watch(() => props.window.x, (val) => { if (!isDragging.value) x.value = val })
watch(() => props.window.y, (val) => { if (!isDragging.value) y.value = val })

const isDragging = ref(false)
const isResizing = ref(false)
/** 当前正在拖拽的缩放角：br=右下 bl=左下 tr=右上 tl=左上 */
type ResizeCorner = 'br' | 'bl' | 'tr' | 'tl'
const resizeCorner = ref<ResizeCorner>('br')
const isClosing = ref(false)
/** 统一隐藏动画（关闭 / 最小化 均走 scale-out transition） */
const isHiding = ref(false)
/** 控制 --entering CSS class：窗口从隐藏变为显示时触发入场动画 */
const isEntering = ref(false)
/** 入场动画是否已完成（transitionend 触发），用于解除 inline transition 屏蔽 */
const enterDone = ref(false)

onMounted(() => {
  // 非特殊窗口（skipEnterAnimation 未设置）且当前为显示态 → 播放入场动画
  if (!props.skipEnterAnimation && !props.window.isMinimized) {
    triggerEnterAnimation()
  } else if (props.skipEnterAnimation) {
    // 特殊窗口（如 AI 助手）：直接标记就绪，跳过入场动画
    enterDone.value = true
  }
})
const rootRef = ref<HTMLElement | null>(null)
const dragStartX = ref(0)
const dragStartY = ref(0)
const windowStartX = ref(0)
const windowStartY = ref(0)
const windowStartWidth = ref(0)
const windowStartHeight = ref(0)

const filterValue = computed(() => {
  return (
    (Object.entries(props.window.filters) as [FilterType, boolean][])
      .filter(([, isEnabled]) => isEnabled)
      .map(([filterType]) => {
        const filterId = props.filterIds[filterType]
        return filterId ? `url(#${filterId})` : null
      })
      .filter((value): value is string => value !== null)
      .join(' ') || undefined
  )
})

let entryRafId: number | undefined

/** 触发入场动画：添加 --entering class，CSS animation 自动播放 */
function triggerEnterAnimation() {
  if (isEntering.value || isClosing.value) return
  console.log(`[动画] 显示 → ${props.window.titleKey}`)
  enterDone.value = false
  isEntering.value = true
}

/** 窗口最小化/恢复时播放入场/退场动画 */
watch(() => props.window.isMinimized, (minimized) => {
  if (minimized) {
    // 可见 → 隐藏：播放 scale-out
    if (!isHiding.value) {
      console.log(`[动画] 隐藏(最小化) → ${props.window.titleKey}`)
      isHiding.value = true
    }
  } else {
    // 隐藏 → 可见：播放 scale-in
    triggerEnterAnimation()
  }
})

onBeforeUnmount(() => {
  if (entryRafId !== undefined) cancelAnimationFrame(entryRafId)
})

function handleMouseDown() {
  if (props.window.isMinimized) return
  emit('focus')
}

function handleCloseClick(event: MouseEvent) {
  event.stopPropagation()
  requestClose()
}

function requestClose() {
  if (!props.window.controls.close) return
  console.log(`[动画] 隐藏(关闭) → ${props.window.titleKey}`)
  isClosing.value = true
  isHiding.value = true
}

function handleAnimationEnd(event: AnimationEvent) {
  if (event.target !== event.currentTarget) return

  if (isClosing.value) {
    console.log(`[动画] 关闭完成 → ${props.window.titleKey}`)
    emit('close')                  // X 关闭 → 通知父组件移除窗口
  }
  if (isHiding.value) {
    console.log(`[动画] 隐藏完成 → ${props.window.titleKey}`)
    isHiding.value = false         // 最小化 → 动画结束，--minimized 静默态接管
  }
  if (isEntering.value) {
    console.log(`[动画] 显示完成 → ${props.window.titleKey}`)
    isEntering.value = false       // 入场完成 → 清除 entering class
    enterDone.value = true         // 入场完成 → 解锁 inline transition
  }
}

function handleMinimizeClick(event: MouseEvent) {
  event.stopPropagation()
  emit('minimize')
}

function handleContentClose() {
  requestClose()
}

/**
 * body 区域拖拽入口。
 * 仅 hideTitlebar 模式下启用（无标题栏时 body 接管拖拽）。
 * 关闭按钮和缩放手柄通过 stopPropagation 排除。
 */
function handleBodyDrag(event: MouseEvent) {
  if (!props.hideTitlebar) return
  startDrag(event)
}

function startDrag(event: MouseEvent) {
  if (props.window.isMinimized) return
  if ((event.target as HTMLElement).closest('.window-frame__control')) return

  event.preventDefault()
  isDragging.value = true
  dragStartX.value = event.clientX
  dragStartY.value = event.clientY
  windowStartX.value = x.value
  windowStartY.value = y.value

  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(event: MouseEvent) {
  if (!isDragging.value) return
  const deltaX = event.clientX - dragStartX.value
  const deltaY = event.clientY - dragStartY.value
  x.value = Math.max(0, windowStartX.value + deltaX)
  y.value = Math.max(0, windowStartY.value + deltaY)
}

function stopDrag() {
  isDragging.value = false
  props.window.x = x.value
  props.window.y = y.value
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

function startResize(event: MouseEvent, corner: ResizeCorner) {
  if (props.window.isMinimized || !props.window.resizable) return
  event.preventDefault()
  event.stopPropagation()
  isResizing.value = true
  resizeCorner.value = corner
  dragStartX.value = event.clientX
  dragStartY.value = event.clientY
  windowStartX.value = x.value
  windowStartY.value = y.value
  windowStartWidth.value = width.value
  windowStartHeight.value = height.value

  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup', stopResize)
}

function startResizeBR(event: MouseEvent) { startResize(event, 'br') }
function startResizeBL(event: MouseEvent) { startResize(event, 'bl') }

function onResize(event: MouseEvent) {
  if (!isResizing.value) return
  // 根据缩放角决定 delta 的正负：左/上边角拖拽时，delta 符号需要反转
  // 例如拖拽左下角向左 → clientX 减小 → rawDeltaX 应为正（窗口变宽）
  const signX = resizeCorner.value.includes('l') ? -1 : 1
  const signY = resizeCorner.value.includes('t') ? -1 : 1
  const rawDeltaX = (event.clientX - dragStartX.value) * signX
  const rawDeltaY = (event.clientY - dragStartY.value) * signY

  if (props.aspectRatio === undefined && props.bodyAspectRatio === undefined) {
    // 自由缩放：delta 直接加到窗口宽高
    const newWidth = Math.max(effectiveMinWidth.value, windowStartWidth.value + rawDeltaX)
    const newHeight = Math.max(effectiveMinHeight.value, windowStartHeight.value + rawDeltaY)
    // 左/上边角拖拽时窗口位置需要同步偏移，保持右下角不动
    if (resizeCorner.value.includes('l')) {
      x.value = windowStartX.value + (windowStartWidth.value - newWidth)
    }
    if (resizeCorner.value.includes('t')) {
      y.value = windowStartY.value + (windowStartHeight.value - newHeight)
    }
    width.value = newWidth
    height.value = newHeight
    return
  }

  // ── 等比缩放 ────────────────────────────────────────
  //
  // 两种模式互斥，aspectRatio 优先：
  //
  // aspectRatio（约束整个窗口）：
  //   windowW / windowH = ratio
  //
  // bodyAspectRatio（约束内容区域，不含标题栏）：
  //   bodyW = windowW - borderOffsetW
  //   bodyH = windowH - borderOffsetH
  //   bodyW / bodyH = ratio
  //
  // 缩放时以鼠标移动方向主导（X 或 Y 中 delta 更大的一方），
  // 另一方向由 ratio 反算。
  const clampW = (v: number) => clamp(v, effectiveMinWidth.value, effectiveMaxWidth.value)
  const clampH = (v: number) => clamp(v, effectiveMinHeight.value, effectiveMaxHeight.value)

  const isWindowRatio = props.aspectRatio !== undefined   // true = 约束窗口；false = 约束 body
  const ratio = isWindowRatio ? props.aspectRatio! : props.bodyAspectRatio!

  // 标题栏 + 边框偏移量（bodyAspectRatio 模式需要从窗口尺寸中扣除）
  // 标题栏高度：34px（.window-frame__titlebar）
  // 边框：左 1px + 右 1px = 2px（width），上 1px + 下 1px = 2px（height 额外）
  const titlebarH = props.hideTitlebar ? 0 : 34
  const borderOffsetW = 2                 // 左右边框各 1px
  const borderOffsetH = titlebarH + 2     // 标题栏 34px + 上下边框各 1px

  if (Math.abs(rawDeltaX) >= Math.abs(rawDeltaY)) {
    // ── X 主导：先确定新宽度，反算高度 ──
    const newWidth = clampW(windowStartWidth.value + rawDeltaX)
    let newHeight: number
    if (isWindowRatio) {
      // aspectRatio：H = W / ratio
      newHeight = newWidth / ratio
    } else {
      // bodyAspectRatio：bodyH = bodyW / ratio → windowH = bodyH + borderOffsetH
      const bodyW = newWidth - borderOffsetW
      const bodyH = bodyW / ratio
      newHeight = clampH(bodyH + borderOffsetH)
    }
    width.value = newWidth
    height.value = newHeight
  } else {
    // ── Y 主导：先确定新高度，反算宽度 ──
    const newHeight = clampH(windowStartHeight.value + rawDeltaY)
    let newWidth: number
    if (isWindowRatio) {
      // aspectRatio：W = H × ratio
      newWidth = newHeight * ratio
    } else {
      // bodyAspectRatio：bodyW = bodyH × ratio → windowW = bodyW + borderOffsetW
      const bodyH = newHeight - borderOffsetH
      const bodyW = bodyH * ratio
      newWidth = clampW(bodyW + borderOffsetW)
    }
    width.value = newWidth
    height.value = newHeight
  }

  // 等比模式下同步调整位置（左/上边角拖拽时窗口会偏移）
  if (resizeCorner.value.includes('l')) {
    x.value = windowStartX.value + (windowStartWidth.value - width.value)
  }
  if (resizeCorner.value.includes('t')) {
    y.value = windowStartY.value + (windowStartHeight.value - height.value)
  }
}

function stopResize() {
  isResizing.value = false
  props.window.width = width.value
  props.window.height = height.value
  props.window.x = x.value
  props.window.y = y.value
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
}
</script>

<template>
  <article
    ref="rootRef"
    class="window-frame"
    :class="{
      'window-frame--active': isActive,
      'window-frame--modal': window.mode === 'modal',
      'window-frame--entering': isEntering,
      'window-frame--hiding': isHiding,
      'window-frame--minimized': window.isMinimized,
      'window-frame--dragging': isDragging,
      'window-frame--resizing': isResizing,
      'window-frame--translucent': props.translucent,
    }"
    :style="{
      left: `${x}px`,
      top: `${y}px`,
      width: `${width}px`,
      height: `${height}px`,
      zIndex: window.zIndex,
      filter: filterValue,
      // 拖拽中/缩放中/隐藏动画中/入场未完成 → 不输出 inline transition
      ...(isDragging || isResizing || isHiding || !enterDone ? {} : { transition: 'left 0.3s ease-out, top 0.3s ease-out' }),
    }"
    :role="window.mode === 'modal' ? 'dialog' : undefined"
    :aria-modal="window.mode === 'modal' ? 'true' : undefined"
    @mousedown="handleMouseDown"
    @animationend="handleAnimationEnd"
  >
    <header
      v-if="!hideTitlebar"
      class="window-frame__titlebar"
      @mousedown="startDrag"
    >
      <span class="window-frame__title">
        <component :is="window.icon" :size="14" :stroke-width="1.8" />
        <span>{{ title ?? t(window.titleKey) }}</span>
      </span>
      <span v-if="window.controls.minimize || window.controls.close || closeAction" class="window-frame__controls">
        <button
          v-if="window.controls.minimize && window.mode === 'normal'"
          class="window-frame__control"
          type="button"
          aria-label="Minimize"
          @click="handleMinimizeClick"
        >
          <Minus :size="14" :stroke-width="1.8" />
        </button>
        <button
          v-if="window.controls.close || closeAction"
          class="window-frame__control window-frame__control--close"
          type="button"
          aria-label="Close"
          @click="closeAction ? closeAction() : handleCloseClick($event)"
        >
          <X :size="14" :stroke-width="1.8" />
        </button>
      </span>
    </header>
    <div class="window-frame__body" @mousedown="handleBodyDrag">
      <component :is="window.component" v-bind="window.componentProps" @close="handleContentClose" />
    </div>
    <span
      v-if="window.resizable"
      class="window-frame__resize-handle window-frame__resize-handle--br"
      aria-hidden="true"
      @mousedown="startResizeBR"
    ></span>
    <span
      v-if="window.resizable"
      class="window-frame__resize-handle window-frame__resize-handle--bl"
      aria-hidden="true"
      @mousedown="startResizeBL"
    ></span>
  </article>
</template>

<style scoped>
.window-frame {
  position: absolute;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line-default);
  background: var(--surface-raised);
  box-shadow: 0 18px 56px rgba(0, 0, 0, 0.45);
  transform-origin: center center;
  transition: border-color 0.16s ease, transform 0.25s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.18s ease;
}

.window-frame--active {
  border-color: var(--signal-red-border);
  box-shadow: 0 22px 64px rgba(0, 0, 0, 0.55);
}

.window-frame--minimized {
  transform: scaleY(0.003);
  opacity: 0;
  pointer-events: none;
}

.window-frame--entering {
  animation: window-open 0.45s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
  pointer-events: none;
}

.window-frame--hiding {
  animation: glitch-tear 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
  pointer-events: none;
  box-shadow:
    4px 0 0 rgba(200, 50, 50, 0.22),
    -4px 0 0 rgba(50, 200, 200, 0.22);
}

.window-frame--dragging,
.window-frame--resizing {
  user-select: none;
}

.window-frame--dragging .window-frame__body,
.window-frame--resizing .window-frame__body {
  pointer-events: none;
}

/* 半透明模式：仅背景透明，内容（图片等）保持不变 */
.window-frame--translucent {
  background: transparent;
  border-color: rgba(74, 74, 85, 0.5);
  box-shadow: none;
}
.window-frame--translucent .window-frame__titlebar {
   background: rgba(32, 32, 38, 0.5);
   border-bottom-color: rgba(43, 43, 51, 0.5);
 }

.window-frame__titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 34px;
  padding: 0 10px;
  border-bottom: 1px solid var(--line-subtle);
  background: var(--surface-panel);
  cursor: move;
  user-select: none;
}

.window-frame__title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font: 600 12px var(--font-ui);
}

.window-frame__controls {
  display: flex;
  align-items: center;
  gap: 2px;
}

.window-frame__control {
  display: grid;
  width: 24px;
  height: 24px;
  place-items: center;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 0;
  color: var(--text-muted);
  background: transparent;
  transition: color 0.12s, background-color 0.12s, border-color 0.12s;
}

.window-frame__control:hover {
  border-color: var(--line-default);
  color: var(--text-primary);
  background: var(--surface-hover);
}

.window-frame__control--close:hover {
  border-color: var(--signal-red);
  color: var(--signal-red);
  background: var(--surface-hover);
}

.window-frame__body {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.window-frame__resize-handle {
  position: absolute;
  width: 14px;
  height: 14px;
  z-index: 1;
}

.window-frame__resize-handle--br {
  right: 0;
  bottom: 0;
  cursor: se-resize;
}

.window-frame__resize-handle--bl {
  left: 0;
  bottom: 0;
  cursor: sw-resize;
}

.window-frame__resize-handle--br::after {
  position: absolute;
  right: 3px;
  width: 5px;
  height: 5px;
  border-right: 1px solid var(--text-muted);
  content: '';
}

.window-frame__resize-handle--bl::after {
  position: absolute;
  left: 3px;
  width: 5px;
  height: 5px;
  border-left: 1px solid var(--text-muted);
  content: '';
}

.window-frame__resize-handle--br::after,
.window-frame__resize-handle--bl::after {
  bottom: 3px;
  border-bottom: 1px solid var(--text-muted);
}

/* ── 窗口动画 ──────────────────────────────────────────── */

@keyframes glitch-tear {
  /* 阶段 1：信号干扰抖动 */
  0%, 5%, 10%   { transform: scaleY(1) translateX(0);   opacity: 1; }
  2.5%          { transform: scaleY(1) translateX(3px);  opacity: 1; }
  7.5%          { transform: scaleY(1) translateX(-3px); opacity: 1; }
  12%           { transform: scaleY(1) translateX(1px);  opacity: 1; }

  /* 阶段 2：色差撕裂保持 */
  15%           { transform: scaleY(1) translateX(0);    opacity: 1; }
  45%           { transform: scaleY(1) translateX(0);    opacity: 1; }

  /* 阶段 3：扫描线压缩 */
  75%           { transform: scaleY(0.003) translateX(0); opacity: 0.4; }

  /* 阶段 4：消失 */
  100%          { transform: scaleY(0.003) translateX(0); opacity: 0; }
}

@keyframes window-open {
  0%   { transform: scale(0.85) translateY(-8px); opacity: 0; }
  100% { transform: scale(1)    translateY(0);    opacity: 1; }
}
</style>
