<script setup lang="ts">
import { computed } from 'vue'

import type { FileTreeNode, FileTreeState } from '@ellia/puzzle-schema'

import { childrenOf, isDirectoryNode, pathFromRoot } from './useFileTree'
import FileTreeLevel from './FileTreeLevel.vue'

const props = defineProps<{
  state: FileTreeState
  selectedId: string | null
  editingNodeIds: Set<string>
}>()

const emit = defineEmits<{
  (e: 'select', nodeId: string): void
  (e: 'add', parentId: string): void
  (e: 'selectParent', parentId: string): void
}>()

const fullChain = computed(() => {
  if (!props.selectedId) return [props.state.rootId]
  return pathFromRoot(props.state, props.selectedId)
})

const chain = computed(() => {
  if (!props.selectedId) return fullChain.value
  const selected = props.state.nodes[props.selectedId]
  // 只有选中的是文件夹时才展开下一层；文件节点只停留在其父层级。
  if (selected && !selected.isDirectory) return fullChain.value.slice(0, -1)
  return fullChain.value
})

const directoryById = computed(() => {
  const map: Record<string, boolean> = {}
  for (const node of Object.values(props.state.nodes)) {
    map[node.id] = isDirectoryNode(node)
  }
  return map
})

function formatParentTitle(parent: FileTreeNode): string {
  if (parent.id === props.state.rootId) return '/'
  const max = 16
  const name = parent.name
  const display = name.length > max ? `${name.slice(0, max - 1)}…` : name
  return `${display}/`
}

const levels = computed(() =>
  chain.value.map((parentId) => {
    const parent = props.state.nodes[parentId]
    return {
      parentId,
      title: parent ? formatParentTitle(parent) : parentId,
      nodes: childrenOf(props.state, parentId),
      canAdd: parent ? Boolean(directoryById.value[parent.id]) : false,
    }
  }),
)
</script>

<template>
  <div class="file-tree-view">
    <FileTreeLevel
      v-for="level in levels"
      :key="level.parentId"
      :title="level.title"
      :parent-id="level.parentId"
      :nodes="level.nodes"
      :selected-id="selectedId"
      :highlighted-ids="chain"
      :editing-node-ids="editingNodeIds"
      :directory-by-id="directoryById"
      :can-add="level.canAdd"
      @select="(node) => emit('select', node.id)"
      @select-parent="(parentId) => emit('selectParent', parentId)"
      @add="(parentId) => emit('add', parentId)"
    />
  </div>
</template>

<style scoped>
.file-tree-view {
  display: flex;
  align-items: stretch;
  height: 100%;
  overflow-x: auto;
  overflow-y: hidden;
}
</style>
