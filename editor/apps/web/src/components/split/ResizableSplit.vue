<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

import SplitDivider from './SplitDivider.vue'

const props = withDefaults(
  defineProps<{
    leftWidth: number
    rightWidth: number
    minLeft?: number
    minRight?: number
  }>(),
  {
    minLeft: 240,
    minRight: 240,
  },
)

const emit = defineEmits<{
  (e: 'update:leftWidth', value: number): void
  (e: 'update:rightWidth', value: number): void
}>()

const dragging = ref<'left' | 'right' | null>(null)
const hoveredDivider = ref<'left' | 'right' | null>(null)
const startX = ref(0)
const startLeft = ref(0)
const startRight = ref(0)

const DEFAULT_DIVIDER_WIDTH = 3
const HOVER_DIVIDER_WIDTH = 7
const HOVER_DELAY_MS = 200

let hoverTimer: ReturnType<typeof setTimeout> | null = null

function dividerWidthFor(side: 'left' | 'right'): number {
  if (dragging.value === side || hoveredDivider.value === side) {
    return HOVER_DIVIDER_WIDTH
  }
  return DEFAULT_DIVIDER_WIDTH
}

function onDividerEnter(side: 'left' | 'right'): void {
  if (dragging.value === side) {
    hoveredDivider.value = side
    return
  }
  if (hoverTimer) clearTimeout(hoverTimer)
  hoverTimer = setTimeout(() => {
    hoveredDivider.value = side
  }, HOVER_DELAY_MS)
}

function onDividerLeave(side: 'left' | 'right'): void {
  if (hoverTimer) {
    clearTimeout(hoverTimer)
    hoverTimer = null
  }
  if (hoveredDivider.value === side) {
    hoveredDivider.value = null
  }
}

function startDrag(side: 'left' | 'right', event: PointerEvent): void {
  if (hoverTimer) {
    clearTimeout(hoverTimer)
    hoverTimer = null
  }
  hoveredDivider.value = side
  dragging.value = side
  startX.value = event.clientX
  startLeft.value = props.leftWidth
  startRight.value = props.rightWidth
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', stopDrag)
}

function onPointerMove(event: PointerEvent): void {
  const dx = event.clientX - startX.value
  if (dragging.value === 'left') {
    emit('update:leftWidth', Math.max(props.minLeft, startLeft.value + dx))
  } else if (dragging.value === 'right') {
    emit('update:rightWidth', Math.max(props.minRight, startRight.value - dx))
  }
}

function stopDrag(): void {
  dragging.value = null
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', stopDrag)
}

onBeforeUnmount(() => {
  if (hoverTimer) clearTimeout(hoverTimer)
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', stopDrag)
})
</script>

<template>
  <div
    class="resizable-split"
    :class="{ 'is-dragging': dragging !== null }"
    :style="{
      gridTemplateColumns: `${leftWidth}px ${dividerWidthFor('left')}px minmax(0, 1fr) ${dividerWidthFor('right')}px ${rightWidth}px`,
    }"
  >
    <div class="pane pane--left">
      <slot name="left" />
    </div>
    <SplitDivider :active="hoveredDivider === 'left' || dragging === 'left'" @mouseenter="onDividerEnter('left')" @mouseleave="onDividerLeave('left')" @drag-start="(event: PointerEvent) => startDrag('left', event)" />
    <div class="pane pane--center">
      <slot name="center" />
    </div>
    <SplitDivider :active="hoveredDivider === 'right' || dragging === 'right'" @mouseenter="onDividerEnter('right')" @mouseleave="onDividerLeave('right')" @drag-start="(event: PointerEvent) => startDrag('right', event)" />
    <div class="pane pane--right">
      <slot name="right" />
    </div>
  </div>
</template>

<style scoped>
.resizable-split {
  display: grid;
  width: 100%;
  height: 100%;
  overflow: hidden;
  transition: grid-template-columns 150ms ease;
}

.pane {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.is-dragging {
  cursor: col-resize;
  user-select: none;
  transition: none;
}
</style>