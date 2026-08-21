<script setup lang="ts">
import { useLayoutStore } from '../stores/layout'
import { useToolPanelStore } from '../stores/toolPanel'
import EntityBrowser from '../components/entity-browser/EntityBrowser.vue'
import EditorPaneHost from '../components/editor/EditorPaneHost.vue'
import SplitResizable from '../components/split/ResizableSplit.vue'
import ToolRail from '../components/tools/ToolRail.vue'
import CreateEntityPanel from '../components/tools/panels/CreateEntityPanel.vue'
import FileManagerPanel from '../components/tools/panels/FileManagerPanel.vue'
import RandomPanel from '../components/tools/panels/RandomPanel.vue'

const layout = useLayoutStore()
const toolPanel = useToolPanelStore()
</script>

<template>
  <SplitResizable
    :left-width="layout.leftWidth"
    :right-width="layout.rightWidth"
    @update:left-width="layout.setLeftWidth"
    @update:right-width="layout.setRightWidth"
  >
    <template #left>
      <EntityBrowser />
    </template>
    <template #center>
      <EditorPaneHost />
    </template>
    <template #right>
      <div class="tool-panel">
        <div class="tool-panel__content">
          <FileManagerPanel v-if="toolPanel.activeTool === 'files'" />
          <CreateEntityPanel v-else-if="toolPanel.activeTool === 'create'" />
          <RandomPanel v-else-if="toolPanel.activeTool === 'random'" />
          <div v-else class="tool-panel__empty">选择一个工具面板</div>
        </div>
        <ToolRail
          :active-tool="toolPanel.activeTool"
          @select="toolPanel.selectTool"
        />
      </div>
    </template>
  </SplitResizable>
</template>

<style scoped>
.tool-panel {
  display: flex;
  height: 100%;
  min-width: 0;
}

.tool-panel__content {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.tool-panel__empty {
  padding: 24px;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}
</style>