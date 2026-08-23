<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import LockOverlay from '../../../presence/LockOverlay.vue'
import DagNodeCard from './DagNodeCard.vue'
import {
  DAG_NODE_HEIGHT,
  DAG_NODE_WIDTH,
  type DagLayoutEdge,
  type DagLayoutNode,
  type DagLayout,
} from './useDag'

const props = defineProps<{
  layout: DagLayout
  selectedId: string | null
  lockHolders: Record<string, string>
}>()

const emit = defineEmits<{
  (e: 'select', nodeId: string): void
  (e: 'add'): void
}>()

const canvasEl = ref<HTMLElement | null>(null)
const zoom = ref(1)
const panX = ref(0)
const panY = ref(0)
const dragging = ref(false)
const dragStart = ref({ x: 0, y: 0, panX: 0, panY: 0 })
const markerId = `dag-arrow-${Math.random().toString(36).slice(2, 10)}`

const worldStyle = computed(() => ({
  width: `${props.layout.width}px`,
  height: `${props.layout.height}px`,
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
}))

function nodeStyle(node: DagLayoutNode): Record<string, string> {
  return {
    left: `${node.x - DAG_NODE_WIDTH / 2}px`,
    top: `${node.y - DAG_NODE_HEIGHT / 2}px`,
    width: `${DAG_NODE_WIDTH}px`,
    height: `${DAG_NODE_HEIGHT}px`,
  }
}

function edgePath(edge: DagLayoutEdge): string {
  if (edge.points.length === 0) return ''
  return edge.points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ')
}

function clampZoom(value: number): number {
  return Math.min(3, Math.max(0.2, value))
}

function fitView(): void {
  const canvas = canvasEl.value
  if (!canvas || props.layout.isEmpty) return
  const rect = canvas.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0 || props.layout.width <= 0 || props.layout.height <= 0) return
  const scale = Math.min(rect.width / props.layout.width, rect.height / props.layout.height, 1)
  zoom.value = Math.max(0.2, scale)
  panX.value = (rect.width - props.layout.width * zoom.value) / 2
  panY.value = (rect.height - props.layout.height * zoom.value) / 2
}

function resetView(): void {
  fitView()
}

function onWheel(event: WheelEvent): void {
  const canvas = canvasEl.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const mouseX = event.clientX - rect.left
  const mouseY = event.clientY - rect.top
  const factor = event.deltaY < 0 ? 1.1 : 1 / 1.1
  const nextZoom = clampZoom(zoom.value * factor)
  const ratio = nextZoom / zoom.value
  panX.value = mouseX - (mouseX - panX.value) * ratio
  panY.value = mouseY - (mouseY - panY.value) * ratio
  zoom.value = nextZoom
}

function onCanvasMouseDown(event: MouseEvent): void {
  if (event.button !== 1) return
  event.preventDefault()
  dragging.value = true
  dragStart.value = {
    x: event.clientX,
    y: event.clientY,
    panX: panX.value,
    panY: panY.value,
  }
}

function onCanvasMouseMove(event: MouseEvent): void {
  if (!dragging.value) return
  panX.value = dragStart.value.panX + (event.clientX - dragStart.value.x)
  panY.value = dragStart.value.panY + (event.clientY - dragStart.value.y)
}

function onCanvasMouseUp(): void {
  dragging.value = false
}

function zoomBy(factor: number): void {
  const canvas = canvasEl.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const mouseX = rect.width / 2
  const mouseY = rect.height / 2
  const nextZoom = clampZoom(zoom.value * factor)
  const ratio = nextZoom / zoom.value
  panX.value = mouseX - (mouseX - panX.value) * ratio
  panY.value = mouseY - (mouseY - panY.value) * ratio
  zoom.value = nextZoom
}

onMounted(() => {
  void nextTick(fitView)
})

watch(
  () => [props.layout.width, props.layout.height],
  () => {
    void nextTick(fitView)
  },
)
</script>

<template>
  <div class="dag-view">
    <div class="dag-view__toolbar">
      <span class="muted">中键拖拽平移 · 滚轮缩放</span>
      <div class="dag-view__zoom-controls">
        <button class="btn btn--text btn--small" type="button" @click="zoomBy(1.2)">＋</button>
        <span class="dag-view__zoom-value">{{ Math.round(zoom * 100) }}%</span>
        <button class="btn btn--text btn--small" type="button" @click="zoomBy(1 / 1.2)">－</button>
        <button class="btn btn--text btn--small" type="button" @click="resetView">适应</button>
      </div>
    </div>

    <div
      ref="canvasEl"
      class="dag-view__canvas"
      :class="{ 'dag-view__canvas--dragging': dragging }"
      @wheel.prevent="onWheel"
      @mousedown="onCanvasMouseDown"
      @mousemove="onCanvasMouseMove"
      @mouseup="onCanvasMouseUp"
      @mouseleave="onCanvasMouseUp"
    >
      <p v-if="layout.isEmpty" class="dag-view__empty">
        暂无 DAG 节点，点击右下角 + 添加节点
      </p>
      <div v-else class="dag-view__world" :style="worldStyle">
        <svg class="dag-view__edges" :width="layout.width" :height="layout.height">
          <defs>
            <marker
              :id="markerId"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path class="dag-view__arrow" d="M 0 0 L 10 5 L 0 10 z" />
            </marker>
          </defs>
          <path
            v-for="edge in layout.edges"
            :key="edge.id"
            class="dag-view__edge"
            :d="edgePath(edge)"
            :marker-end="`url(#${markerId})`"
          />
        </svg>

        <div
          v-for="node in layout.nodes"
          :key="node.id"
          class="dag-view__node"
          :style="nodeStyle(node)"
        >
          <DagNodeCard
            :node="node"
            :selected="node.id === selectedId"
            @select="$emit('select', node.id)"
          />
          <LockOverlay v-if="lockHolders[node.id]" :username="lockHolders[node.id] ?? ''" />
        </div>

      </div>

      <button class="dag-view__fab" type="button" title="添加 DAG 节点" @click="$emit('add')">
        ＋
      </button>
    </div>
  </div>
</template>

<style scoped>
.dag-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  box-sizing: border-box;
  overflow: hidden;
}

.dag-view__toolbar {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
}

.dag-view__zoom-controls {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.dag-view__zoom-value {
  min-width: 44px;
  text-align: center;
  font-size: 0.78rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.dag-view__canvas {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
  cursor: grab;
  user-select: none;
}

.dag-view__canvas--dragging {
  cursor: grabbing;
}

.dag-view__world {
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: 0 0;
}

.dag-view__edges {
  position: absolute;
  top: 0;
  left: 0;
  overflow: visible;
  pointer-events: none;
}

.dag-view__edge {
  fill: none;
  stroke: var(--md-sys-color-outline-variant, #cac4d0);
  stroke-width: 1.5;
}

.dag-view__arrow {
  fill: var(--md-sys-color-outline-variant, #cac4d0);
}

.dag-view__node {
  position: absolute;
  z-index: 1;
}

.dag-view__empty {
  margin: 0;
  padding: 32px;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  text-align: center;
}

.dag-view__fab {
  position: absolute;
  right: 16px;
  bottom: 16px;
  z-index: 5;
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 16px;
  background: var(--md-sys-color-primary-container, #eaddff);
  color: var(--md-sys-color-on-primary-container, #21005d);
  font-size: 1.4rem;
  line-height: 1;
  box-shadow: 0 2px 8px var(--app-shadow, rgba(0, 0, 0, 0.12));
  cursor: pointer;
  transition: background-color 0.15s ease, transform 0.15s ease;
}

.dag-view__fab:hover {
  background: var(--md-sys-color-primary, #6750a4);
  color: var(--md-sys-color-on-primary, #ffffff);
}

.dag-view__fab:active {
  transform: scale(0.96);
}
</style>
