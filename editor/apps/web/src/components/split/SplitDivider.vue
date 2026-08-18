<script setup lang="ts">
defineProps<{
  active?: boolean
}>()

const emit = defineEmits<{
  (e: 'drag-start', event: PointerEvent): void
}>()

function onPointerDown(event: PointerEvent): void {
  event.preventDefault()
  emit('drag-start', event)
}
</script>

<template>
  <div
    class="split-divider"
    :class="{ 'split-divider--active': active }"
    role="separator"
    aria-orientation="vertical"
    @pointerdown="onPointerDown"
  />
</template>

<style scoped>
.split-divider {
  width: 100%;
  height: 100%;
  cursor: col-resize;
  background: var(--md-sys-color-outline-variant, #cac4d0);
  flex: none;
  touch-action: none;
  user-select: none;
  transition:
    background-color 150ms ease,
    width 150ms ease;
}

.split-divider--active {
  background: var(--md-sys-color-primary, #6750a4);
}
</style>