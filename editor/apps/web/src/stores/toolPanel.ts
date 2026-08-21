import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ToolId = 'files' | 'create' | 'random'

export const useToolPanelStore = defineStore('toolPanel', () => {
  const activeTool = ref<ToolId | null>('files')

  function selectTool(tool: ToolId | null): void {
    activeTool.value = tool
  }

  return {
    activeTool,
    selectTool,
  }
})