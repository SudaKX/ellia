<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { syncClient } from '../client/ws'
import { useEditorTabsStore } from '../stores/editorTabs'
import { useEntitiesStore } from '../stores/entities'
import { useLayoutStore } from '../stores/layout'
import { useLocksStore } from '../stores/locks'
import { usePresenceStore } from '../stores/presence'
import { useProjectsStore } from '../stores/projects'
import EditorLayout from '../layouts/EditorLayout.vue'

const route = useRoute()
const projectsStore = useProjectsStore()
const entitiesStore = useEntitiesStore()
const layoutStore = useLayoutStore()
const locksStore = useLocksStore()
const presenceStore = usePresenceStore()
const tabsStore = useEditorTabsStore()

const error = ref<string | null>(null)
const ready = ref(false)
let openUnsub: (() => void) | null = null

const projectId = String(route.params.id ?? '')

async function initialize(): Promise<void> {
  error.value = null
  try {
    await projectsStore.loadProject(projectId)
    entitiesStore.initialize(projectId)
    layoutStore.initialize(projectId)
    locksStore.ensureSubscriptions()
    presenceStore.ensureSubscriptions()

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${protocol}://${window.location.host}/ws/projects/${encodeURIComponent(projectId)}`
    openUnsub = syncClient.onOpen(() => {
      syncClient.join(projectId, entitiesStore.vector as Record<string, number>)
    })
    syncClient.connect(wsUrl)

    ready.value = true
  } catch (err) {
    error.value = err instanceof Error ? err.message : '项目加载失败'
  }
}

void initialize()

onUnmounted(() => {
  openUnsub?.()
  tabsStore.clear()
  locksStore.clear()
  syncClient.disconnect()
  presenceStore.clear()
  entitiesStore.clear()
})
</script>

<template>
  <div class="project-view">
    <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    <p v-else-if="!ready" class="muted">正在加载项目…</p>
    <EditorLayout v-else />
  </div>
</template>

<style scoped>
.project-view {
  height: 100vh;
  overflow: hidden;
}
</style>