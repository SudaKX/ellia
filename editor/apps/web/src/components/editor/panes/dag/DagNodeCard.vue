<script setup lang="ts">
import type { DagLayoutNode } from './useDag'

defineProps<{
  node: DagLayoutNode
  selected?: boolean
}>()

defineEmits<{
  (e: 'select'): void
}>()
</script>

<template>
  <button
    type="button"
    class="dag-node-card"
    :class="{
      'dag-node-card--selected': selected,
      'dag-node-card--missing': node.isMissing,
      'dag-node-card--entry': node.isEntry,
    }"
    :title="`${node.name}\n${node.resourceId ?? ''}`"
    @click.left="$emit('select')"
  >
    <span class="dag-node-card__badges">
      <span v-if="node.isEntry" class="dag-node-card__badge dag-node-card__badge--entry">入口</span>
      <span v-if="node.isMissing" class="dag-node-card__badge dag-node-card__badge--missing">缺失</span>
    </span>
    <span class="dag-node-card__main">{{ node.name }}</span>
    <span class="dag-node-card__sub">{{ node.resourceId ?? '未关联' }}</span>
  </button>
</template>

<style scoped>
.dag-node-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 2px;
  width: 100%;
  height: 100%;
  padding: 6px 10px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 10px;
  background: transparent;
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
  cursor: pointer;
  overflow: hidden;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.dag-node-card:hover {
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.dag-node-card--selected {
  border-color: var(--md-sys-color-primary, #6750a4);
}

.dag-node-card--selected:hover {
  background: var(--md-sys-color-primary-container, #eaddff);
}

.dag-node-card--missing {
  border-style: dashed;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.dag-node-card__badges {
  position: absolute;
  top: 2px;
  right: 4px;
  display: inline-flex;
  gap: 3px;
}

.dag-node-card__badge {
  font-size: 0.6rem;
  line-height: 1.2;
  padding: 1px 4px;
  border-radius: 999px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.dag-node-card__badge--entry {
  background: var(--md-sys-color-primary-container, #eaddff);
  color: var(--md-sys-color-on-primary-container, #21005d);
}

.dag-node-card__badge--missing {
  background: var(--md-sys-color-error-container, #f9dedc);
  color: var(--md-sys-color-on-error-container, #410e0b);
}

.dag-node-card__main,
.dag-node-card__sub {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dag-node-card__main {
  font-size: 0.8rem;
  font-weight: 600;
  padding-right: 40px;
}

.dag-node-card__sub {
  font-size: 0.68rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}
</style>
