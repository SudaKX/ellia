<script setup lang="ts">
import { computed, ref } from 'vue'
import { ZoomIn, ZoomOut, Maximize } from 'lucide-vue-next'

/**
 * 图片浏览窗口：在独立窗口内查看图片（立绘等）。
 *
 * - **滚轮缩放**：以鼠标位置为锚点放大/缩小（向上滚放大、向下滚缩小）；
 * - **鼠标拖动**：按住左键拖动平移图片（放大后可拖到任意位置查看）；
 * - 工具栏按钮：放大 / 缩小 / 适应窗口（重置缩放与平移）；
 * - 双击图片文件（FileNode.image，如 home/形象工程/初稿.png）时由 FileExplorer 打开。
 */
const props = defineProps<{
  /** 图片 URL（如 /console/images/ellia_big/ellia_3.png） */
  imageUrl: string
  /** 文件名（窗口标题 / 备用文本） */
  fileName?: string
}>()

const MIN_SCALE = 0.25
const MAX_SCALE = 16
const WHEEL_FACTOR = 1.1
const BUTTON_FACTOR = 1.25

const scale = ref(1)
/** 平移偏移（相对图片中心，px） */
const offset = ref({ x: 0, y: 0 })
const stageRef = ref<HTMLElement | null>(null)
const dragging = ref(false)
const dragStart = ref({ x: 0, y: 0, ox: 0, oy: 0 })

/**
 * 以屏幕上某点为锚点缩放：缩放后该点下的图片内容保持不动。
 * 锚点取不到（按钮调用）时用舞台中心。
 */
function zoomAt(factor: number, clientX: number, clientY: number) {
  const stage = stageRef.value
  if (!stage) return
  const rect = stage.getBoundingClientRect()
  const mx = clientX - rect.left - rect.width / 2
  const my = clientY - rect.top - rect.height / 2
  // 锚点在图片坐标系中的位置（相对图片中心，未缩放单位）
  const pix = (mx - offset.value.x) / scale.value
  const piy = (my - offset.value.y) / scale.value
  const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale.value * factor))
  if (next === scale.value) return
  scale.value = next
  offset.value = { x: mx - pix * next, y: my - piy * next }
}

/** 滚轮：向上滚放大、向下滚缩小（以鼠标为锚点） */
function handleWheel(e: WheelEvent) {
  zoomAt(e.deltaY < 0 ? WHEEL_FACTOR : 1 / WHEEL_FACTOR, e.clientX, e.clientY)
}

/** 工具栏放大（以舞台中心为锚点） */
function zoomIn() {
  const stage = stageRef.value
  if (!stage) return
  const rect = stage.getBoundingClientRect()
  zoomAt(BUTTON_FACTOR, rect.left + rect.width / 2, rect.top + rect.height / 2)
}

/** 工具栏缩小（以舞台中心为锚点） */
function zoomOut() {
  const stage = stageRef.value
  if (!stage) return
  const rect = stage.getBoundingClientRect()
  zoomAt(1 / BUTTON_FACTOR, rect.left + rect.width / 2, rect.top + rect.height / 2)
}

/** 重置为适应窗口（缩放 1、平移归零） */
function reset() {
  scale.value = 1
  offset.value = { x: 0, y: 0 }
}

// ─── 拖拽平移 ──────────────────────────────────────

function handleMouseDown(e: MouseEvent) {
  if (e.button !== 0) return
  dragging.value = true
  dragStart.value = { x: e.clientX, y: e.clientY, ox: offset.value.x, oy: offset.value.y }
}

function handleMouseMove(e: MouseEvent) {
  if (!dragging.value) return
  offset.value = {
    x: dragStart.value.ox + (e.clientX - dragStart.value.x),
    y: dragStart.value.oy + (e.clientY - dragStart.value.y),
  }
}

function handleMouseUp() {
  dragging.value = false
}

const zoomLabel = computed(() => `${Math.round(scale.value * 100)}%`)

/** 图片 transform：先居中（-50%）再平移再缩放 */
const imgStyle = computed(() => ({
  transform: `translate(-50%, -50%) translate(${offset.value.x}px, ${offset.value.y}px) scale(${scale.value})`,
}))
</script>

<template>
  <div class="image-viewer">
    <div class="image-viewer__toolbar">
      <span class="image-viewer__name">{{ fileName ?? '' }}</span>
      <div class="image-viewer__tools">
        <button class="image-viewer__btn" type="button" title="缩小" @click="zoomOut">
          <ZoomOut :size="14" :stroke-width="1.8" />
        </button>
        <span class="image-viewer__zoom">{{ zoomLabel }}</span>
        <button class="image-viewer__btn" type="button" title="放大" @click="zoomIn">
          <ZoomIn :size="14" :stroke-width="1.8" />
        </button>
        <button class="image-viewer__btn" type="button" title="适应窗口" @click="reset">
          <Maximize :size="14" :stroke-width="1.8" />
        </button>
      </div>
    </div>
    <div
      ref="stageRef"
      class="image-viewer__stage"
      :class="{ 'image-viewer__stage--dragging': dragging }"
      @wheel.prevent="handleWheel"
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @mouseleave="handleMouseUp"
    >
      <img
        :src="imageUrl"
        :alt="fileName ?? 'image'"
        class="image-viewer__image"
        :style="imgStyle"
        draggable="false"
      />
    </div>
  </div>
</template>

<style scoped>
.image-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--canvas);
}

.image-viewer__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 12px;
  border-bottom: 1px solid var(--line-subtle);
}

.image-viewer__name {
  overflow: hidden;
  color: var(--text-secondary);
  font: 12px var(--font-ui);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.image-viewer__tools {
  display: flex;
  align-items: center;
  gap: 4px;
}

.image-viewer__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 24px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-secondary);
  background: var(--surface-panel);
  cursor: pointer;
  transition: color 0.12s, background-color 0.12s, border-color 0.12s;
}

.image-viewer__btn:hover {
  border-color: var(--signal-red);
  color: var(--text-primary);
  background: var(--surface-hover);
}

.image-viewer__zoom {
  min-width: 46px;
  color: var(--text-secondary);
  font: 12px var(--font-mono);
  text-align: center;
}

.image-viewer__stage {
  position: relative;
  flex: 1;
  overflow: hidden;
  cursor: grab;
  background: linear-gradient(180deg, var(--surface-raised), var(--canvas));
}

.image-viewer__stage--dragging {
  cursor: grabbing;
}

.image-viewer__image {
  position: absolute;
  top: 50%;
  left: 50%;
  display: block;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transform-origin: center center;
  user-select: none;
}
</style>
