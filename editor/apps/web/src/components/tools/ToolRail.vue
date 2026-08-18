<script setup lang="ts">
import type { ToolId } from '../../stores/toolPanel'

const props = defineProps<{
  activeTool: ToolId | null
}>()

const emit = defineEmits<{
  (e: 'select', tool: ToolId | null): void
}>()

const tools: Array<{ id: ToolId; label: string; icon: string }> = [
  { id: 'files', label: '文件管理', icon: '📁' },
  { id: 'create', label: '创建实体', icon: '➕' },
]
</script>

<template>
  <nav class="tool-rail" aria-label="工具面板">
    <button
      v-for="tool in tools"
      :key="tool.id"
      type="button"
      class="tool-rail__button"
      :class="{ 'tool-rail__button--active': activeTool === tool.id }"
      :title="tool.label"
      :aria-label="tool.label"
      @click="emit('select', activeTool === tool.id ? null : tool.id)"
    >
      <span aria-hidden="true">{{ tool.icon }}</span>
    </button>
  </nav>
</template>

<style scoped>
.tool-rail {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 44px;
  padding: 8px 4px;
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
  border-left: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
}

.tool-rail__button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-size: 1.1rem;
  cursor: pointer;
}

.tool-rail__button:hover {
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.tool-rail__button--active {
  background: var(--md-sys-color-secondary-container, #e8def8);
}
</style>