<script setup lang="ts">
import { Minus, X } from 'lucide-vue-next'
import { ref } from 'vue'

import type { WindowInstance } from '@/types/desktop'

const props = defineProps<{
  window: WindowInstance
  isActive: boolean
}>()

const emit = defineEmits<{
  close: []
  focus: []
  minimize: []
}>()

const MIN_WIDTH = 260
const MIN_HEIGHT = 160

const x = ref(props.window.x)
const y = ref(props.window.y)
const width = ref(props.window.width)
const height = ref(props.window.height)

const isDragging = ref(false)
const isResizing = ref(false)
const isClosing = ref(false)
const dragStartX = ref(0)
const dragStartY = ref(0)
const windowStartX = ref(0)
const windowStartY = ref(0)
const windowStartWidth = ref(0)
const windowStartHeight = ref(0)

function handleMouseDown() {
  if (props.window.isMinimized) return
  emit('focus')
}

function handleCloseClick(event: MouseEvent) {
  event.stopPropagation()
  isClosing.value = true
}

function handleTransitionEnd(event: TransitionEvent) {
  if (event.target === event.currentTarget && event.propertyName === 'transform' && isClosing.value) {
    emit('close')
  }
}

function handleMinimizeClick(event: MouseEvent) {
  event.stopPropagation()
  emit('minimize')
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

function startResize(event: MouseEvent) {
  if (props.window.isMinimized) return
  event.preventDefault()
  event.stopPropagation()
  isResizing.value = true
  dragStartX.value = event.clientX
  dragStartY.value = event.clientY
  windowStartWidth.value = width.value
  windowStartHeight.value = height.value

  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup', stopResize)
}

function onResize(event: MouseEvent) {
  if (!isResizing.value) return
  const deltaX = event.clientX - dragStartX.value
  const deltaY = event.clientY - dragStartY.value
  width.value = Math.max(MIN_WIDTH, windowStartWidth.value + deltaX)
  height.value = Math.max(MIN_HEIGHT, windowStartHeight.value + deltaY)
}

function stopResize() {
  isResizing.value = false
  props.window.width = width.value
  props.window.height = height.value
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
}
</script>

<template>
  <article
    class="window-frame"
    :class="{
      'window-frame--active': isActive,
      'window-frame--closing': isClosing,
      'window-frame--minimized': window.isMinimized,
      'window-frame--dragging': isDragging,
      'window-frame--resizing': isResizing,
    }"
    :style="{
      left: `${x}px`,
      top: `${y}px`,
      width: `${width}px`,
      height: `${height}px`,
      zIndex: window.zIndex,
    }"
    @mousedown="handleMouseDown"
    @transitionend="handleTransitionEnd"
  >
    <header class="window-frame__titlebar" @mousedown="startDrag">
      <span class="window-frame__title">
        <component :is="window.icon" :size="14" :stroke-width="1.8" />
        <span>{{ window.title }}</span>
      </span>
      <span class="window-frame__controls">
        <button
          class="window-frame__control"
          type="button"
          aria-label="Minimize"
          @click="handleMinimizeClick"
        >
          <Minus :size="14" :stroke-width="1.8" />
        </button>
        <button
          class="window-frame__control window-frame__control--close"
          type="button"
          aria-label="Close"
          @click="handleCloseClick"
        >
          <X :size="14" :stroke-width="1.8" />
        </button>
      </span>
    </header>
    <div class="window-frame__body">
      <component :is="window.component" />
    </div>
    <span class="window-frame__resize-handle" aria-hidden="true" @mousedown="startResize"></span>
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
  transform: scaleY(0);
  opacity: 0;
  pointer-events: none;
}

.window-frame--closing {
  transform: scale(0.4);
  opacity: 0;
  pointer-events: none;
}

.window-frame--dragging,
.window-frame--resizing {
  user-select: none;
}

.window-frame--dragging .window-frame__body,
.window-frame--resizing .window-frame__body {
  pointer-events: none;
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
  right: 0;
  bottom: 0;
  width: 14px;
  height: 14px;
  cursor: se-resize;
}

.window-frame__resize-handle::after {
  position: absolute;
  right: 3px;
  bottom: 3px;
  width: 5px;
  height: 5px;
  border-right: 1px solid var(--text-muted);
  border-bottom: 1px solid var(--text-muted);
  content: '';
}
</style>
