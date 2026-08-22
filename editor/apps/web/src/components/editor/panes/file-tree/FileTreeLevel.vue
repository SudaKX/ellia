<script setup lang="ts">
import type { FileTreeNode } from '@ellia/puzzle-schema'

import TreeNodeCard from './TreeNodeCard.vue'

defineProps<{
  title: string
  parentId: string
  nodes: FileTreeNode[]
  selectedId: string | null
  highlightedIds: string[]
  editingNodeIds: Set<string>
  directoryById: Record<string, boolean>
  canAdd: boolean
}>()

defineEmits<{
  (e: 'select', node: FileTreeNode): void
  (e: 'selectParent', parentId: string): void
  (e: 'add', parentId: string): void
}>()
</script>

<template>
  <section class="file-tree-level">
    <header class="file-tree-level__header">
      <button type="button" class="file-tree-level__parent" @click="$emit('selectParent', parentId)">
        {{ title }}
      </button>
    </header>

    <div class="file-tree-level__list">
      <TreeNodeCard
        v-for="node in nodes"
        :key="node.id"
        :node="node"
        :selected="node.id === selectedId"
        :highlighted="highlightedIds.includes(node.id)"
        :editing="editingNodeIds.has(node.id)"
        :directory="Boolean(directoryById[node.id])"
        @select="$emit('select', node)"
      />
      <p v-if="nodes.length === 0" class="file-tree-level__empty">空目录</p>
    </div>

    <footer class="file-tree-level__footer">
      <button
        v-if="canAdd"
        type="button"
        class="file-tree-level__add"
        @click="$emit('add', parentId)"
      >
        + 添加节点
      </button>
    </footer>
  </section>
</template>

<style scoped>
.file-tree-level {
  display: flex;
  flex-direction: column;
  max-width: 180px;
  height: 100%;
  border-right: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
  box-sizing: border-box;
}

.file-tree-level__header {
  flex: none;
  padding: 8px 10px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
}

.file-tree-level__parent {
  border: none;
  background: transparent;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font: inherit;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.file-tree-level__list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
}

.file-tree-level__empty {
  margin: 0;
  padding: 12px 4px;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font-size: 0.8rem;
  text-align: center;
}

.file-tree-level__footer {
  flex: none;
  padding: 8px;
}

.file-tree-level__add {
  width: 100%;
  min-height: 32px;
  border: 1px dashed var(--md-sys-color-outline, #79747e);
  border-radius: 8px;
  background: transparent;
  color: var(--md-sys-color-primary, #6750a4);
  cursor: pointer;
  font: inherit;
  font-size: 0.8rem;
  white-space: nowrap;
}

.file-tree-level__add:hover {
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}
</style>
