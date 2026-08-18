<script setup lang="ts">
import { computed } from 'vue'

import { useEditorTabsStore } from '../../stores/editorTabs'
import { useEntitiesStore } from '../../stores/entities'
import { resolveEditorForEntity } from './registry'
import EditorActionBar from './EditorActionBar.vue'
import EditorTabBar from './EditorTabBar.vue'

const tabsStore = useEditorTabsStore()
const entitiesStore = useEntitiesStore()

const activeEntity = computed(
  () =>
    (tabsStore.activeEntityId
      ? entitiesStore.entities[tabsStore.activeEntityId]
      : undefined) ?? null,
)

const currentEditorComponent = computed(() =>
  activeEntity.value ? resolveEditorForEntity(activeEntity.value) : null,
)

function onDeleted(entityId: string): void {
  tabsStore.closeTab(entityId)
}
</script>

<template>
  <div class="editor-pane-host">
    <EditorTabBar
      v-if="tabsStore.tabs.length > 0"
      :tabs="tabsStore.tabs"
      :active-entity-id="tabsStore.activeEntityId"
      @activate="tabsStore.activateTab"
      @close="tabsStore.closeTab"
    />
    <EditorActionBar
      v-if="tabsStore.tabs.length > 0"
      :entity="activeEntity"
      @deleted="onDeleted"
    />
    <div class="editor-pane-host__body">
      <KeepAlive v-if="activeEntity">
        <component
          :is="currentEditorComponent"
          :key="activeEntity.id"
          :entity="activeEntity"
        />
      </KeepAlive>
      <div v-else class="editor-pane-host__empty">打开左侧实体开始编辑</div>
    </div>
  </div>
</template>

<style scoped>
.editor-pane-host {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
}

.editor-pane-host__body {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.editor-pane-host__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}
</style>