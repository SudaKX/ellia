<script setup lang="ts">
import { useTooltipStore } from '../../stores/tooltip'

const tooltip = useTooltipStore()
</script>

<template>
  <Teleport to="body">
    <div v-if="tooltip.visible" class="app-tooltip-overlay">
      <div class="app-tooltip" :style="tooltip.position ?? undefined">
        {{ tooltip.text }}
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.app-tooltip-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  pointer-events: none;
}

.app-tooltip {
  position: absolute;
  transform: translateX(-50%);
  max-width: 280px;
  padding: 6px 8px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font-size: 0.75rem;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.15);
  pointer-events: none;
}
</style>
