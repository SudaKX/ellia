<script setup lang="ts">
import type { EditorTab } from '../../stores/editorTabs'
import { useEntitiesStore } from '../../stores/entities'

const props = defineProps<{
  tabs: EditorTab[]
  activeEntityId: string | null
}>()

const emit = defineEmits<{
  (e: 'activate', entityId: string): void
  (e: 'close', entityId: string): void
}>()

const entitiesStore = useEntitiesStore()

function tabTitle(tab: EditorTab): string {
  const entity = entitiesStore.entities[tab.entityId]
  return entity?.resource_id ?? tab.title
}
</script>

<template>
  <div class="editor-tabbar" role="tablist" aria-label="打开的编辑器">
    <button
      v-for="tab in tabs"
      :key="tab.entityId"
      type="button"
      class="editor-tab"
      :class="{ 'editor-tab--active': tab.entityId === activeEntityId }"
      role="tab"
      :aria-selected="tab.entityId === activeEntityId"
      @click="emit('activate', tab.entityId)"
    >
      <span class="editor-tab__title">{{ tabTitle(tab) }}</span>
      <span
        class="editor-tab__close"
        role="button"
        aria-label="关闭标签"
        @click.stop="emit('close', tab.entityId)"
      >
        ×
      </span>
    </button>
  </div>
</template>

<style scoped>
.editor-tabbar {
  display: flex;
  align-items: stretch;
  gap: 4px;
  padding: 4px 6px 0;
  border-bottom: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
  overflow-x: auto;
}

.editor-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px 6px 12px;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: transparent;
  color: var(--md-sys-color-on-surface, #1d1b20);
  cursor: pointer;
  white-space: nowrap;
  max-width: 220px;
}

.editor-tab--active {
  background: var(--md-sys-color-surface-container, #f3edf7);
  border-color: var(--md-sys-color-outline-variant, #cac4d0);
}

.editor-tab__title {
  overflow: hidden;
  text-overflow: ellipsis;
}

.editor-tab__close {
  font-size: 1rem;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 4px;
}

.editor-tab__close:hover {
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}
</style>