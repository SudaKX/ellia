<script setup lang="ts">
import type { FileTreeNode } from '@ellia/puzzle-schema'

defineProps<{
  node: FileTreeNode
  selected?: boolean
  highlighted?: boolean
  directory?: boolean
}>()

defineEmits<{
  (e: 'select'): void
}>()
</script>

<template>
  <button
    type="button"
    class="tree-node-card"
    :class="{
      'tree-node-card--selected': selected,
      'tree-node-card--highlighted': highlighted,
    }"
    @click="$emit('select')"
  >
    <span class="tree-node-card__icon" aria-hidden="true">{{ directory ? '📁' : '📄' }}</span>
    <span class="tree-node-card__name">{{ node.name }}</span>
  </button>
</template>

<style scoped>
.tree-node-card {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-height: 32px;
  padding: 4px 8px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  text-align: left;
  cursor: pointer;
  font: inherit;
}

.tree-node-card:hover {
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.tree-node-card--highlighted {
  border-color: var(--md-sys-color-tertiary, #7d5260);
  color: var(--md-sys-color-on-tertiary-container, #31111d);
}

.tree-node-card--highlighted:hover {
  background: var(--md-sys-color-tertiary-container, #ffd8e4);
}

.tree-node-card--selected {
  border-color: var(--md-sys-color-primary, #6750a4);
  color: var(--md-sys-color-on-primary-container, #21005d);
}

.tree-node-card--selected:hover {
  background: var(--md-sys-color-primary-container, #eaddff);
}

.tree-node-card__icon {
  flex: none;
  font-size: 0.9rem;
}

.tree-node-card__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.8rem;
  font-weight: 600;
}
</style>
