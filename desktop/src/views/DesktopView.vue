<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Archive, FileText, LockKeyhole, TerminalSquare } from 'lucide-vue-next'

import DesktopStatusBar from '@/components/desktop/DesktopStatusBar.vue'
import DockBar from '@/components/desktop/DockBar.vue'
import type { DockApplicationState } from '@/components/desktop/DockBar.vue'
import Launchpad from '@/components/desktop/Launchpad.vue'
import WindowFrame from '@/components/desktop/WindowFrame.vue'
import FileExplorer from '@/components/applications/FileExplorer.vue'
import ArchiveViewer from '@/components/applications/ArchiveViewer.vue'
import Terminal from '@/components/applications/Terminal.vue'
import SandboxControl from '@/components/applications/SandboxControl.vue'
import { useFilterService } from '@/composables/useFilterService'
import { useWindowService } from '@/composables/useWindowService'
import { useDesktopStore } from '@/stores/desktop'
import type { ApplicationId } from '@/types/desktop'

const desktop = useDesktopStore()
const windowService = useWindowService()
const filterService = useFilterService()
const glitchFilter = filterService.create('glitch', {
  intensity: 2,
  frequencyX: 0.002,
  frequencyY: 0.05,
  enableHorizontalDisplacement: true,
  enableVerticalDisplacement: false,
  animate: false,
  frameSkip: 24,
})

watch(
  () => desktop.isApplicationOverviewOpen,
  (isOpen) => {
    filterService.update(glitchFilter.instanceId, { animate: isOpen })
  },
)

const applicationRegistry: Record<ApplicationId, { title: string }> = {
  files: { title: 'File Explorer' },
  archive: { title: 'Archive Viewer' },
  terminal: { title: 'Command Terminal' },
  sandbox: { title: 'Sandbox Control' },
}

windowService.registerApplication({
  id: 'files',
  title: applicationRegistry.files.title,
  icon: FileText,
  component: FileExplorer,
  defaultWidth: 420,
  defaultHeight: 280,
})

windowService.registerApplication({
  id: 'archive',
  title: applicationRegistry.archive.title,
  icon: Archive,
  component: ArchiveViewer,
  defaultWidth: 460,
  defaultHeight: 300,
})

windowService.registerApplication({
  id: 'terminal',
  title: applicationRegistry.terminal.title,
  icon: TerminalSquare,
  component: Terminal,
  defaultWidth: 560,
  defaultHeight: 340,
})

windowService.registerApplication({
  id: 'sandbox',
  title: applicationRegistry.sandbox.title,
  icon: LockKeyhole,
  component: SandboxControl,
  defaultWidth: 400,
  defaultHeight: 260,
})

const time = ref('00:00:00')
let clockTimer: number | undefined

function updateTime() {
  time.value = new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date())
}

function handleLaunch(applicationId: ApplicationId) {
  windowService.open(applicationId)
  desktop.closeApplicationOverview()
}

function handleShowAll() {
  desktop.toggleApplicationOverview()
}

function handleCloseOverview() {
  desktop.closeApplicationOverview()
}

const applicationStates = computed<DockApplicationState[]>(() => {
  return windowService.openApplicationIds.value.map((applicationId) => {
    const windows = windowService.windows.value.filter(
      (window) => window.applicationId === applicationId,
    )
    const hasFocused = windows.some((window) => window.id === windowService.activeWindowId.value)
    const hasForeground = windows.some((window) => !window.isMinimized)

    let state: DockApplicationState['state']
    if (hasFocused && hasForeground) {
      state = 'focused'
    } else if (hasForeground) {
      state = 'foreground'
    } else {
      state = 'minimized'
    }

    return {
      applicationId,
      name: applicationRegistry[applicationId].title,
      state,
    }
  })
})

function handleDockAppClick(applicationId: ApplicationId) {
  const windows = windowService.windows.value.filter(
    (window) => window.applicationId === applicationId,
  )
  const hasFocused = windows.some((window) => window.id === windowService.activeWindowId.value)
  const hasForeground = windows.some((window) => !window.isMinimized)

  if (hasFocused && hasForeground) {
    const focusedWindow = windows.find((window) => window.id === windowService.activeWindowId.value)
    if (focusedWindow) {
      windowService.minimize(focusedWindow.id)
    }
  } else if (hasForeground) {
    const topWindow = windows.slice().sort((a, b) => b.zIndex - a.zIndex)[0]
    if (topWindow) {
      windowService.focus(topWindow.id)
    }
  } else {
    windowService.open(applicationId)
  }
}

onMounted(() => {
  updateTime()
  clockTimer = window.setInterval(updateTime, 1000)
})

onBeforeUnmount(() => {
  window.clearInterval(clockTimer)
  filterService.destroy(glitchFilter.instanceId)
})
</script>

<template>
  <main class="desktop-shell">
    <DesktopStatusBar :time="time" />

    <section class="desktop-workspace" aria-label="FakeOS desktop workspace">
      <div class="workspace-grid" aria-hidden="true"></div>

      <WindowFrame
        v-for="window in windowService.windows.value"
        :key="window.id"
        :window="window"
        :is-active="windowService.activeWindowId.value === window.id"
        @close="windowService.close(window.id)"
        @focus="windowService.focus(window.id)"
        @minimize="windowService.minimize(window.id)"
      />
    </section>

    <Transition name="launchpad">
      <Launchpad
        v-if="desktop.isApplicationOverviewOpen"
        :applications="desktop.applications"
        :filter-id="glitchFilter.filterId"
        @close="handleCloseOverview"
        @launch="handleLaunch"
      />
    </Transition>

    <DockBar
      :application-states="applicationStates"
      @click="handleDockAppClick"
      @show-all="handleShowAll"
    />
  </main>
</template>

<style scoped>
.desktop-shell {
  position: relative;
  display: grid;
  grid-template-rows: auto 1fr;
  min-height: 100dvh;
  overflow: hidden;
  background: var(--canvas);
}

.desktop-workspace {
  position: relative;
  min-height: 0;
  overflow: hidden;
}

.workspace-grid {
  position: absolute;
  inset: 0;
  opacity: 0.22;
  background-image: linear-gradient(var(--grid-line) 1px, transparent 1px), linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(to bottom, transparent, black 14%, black 88%, transparent);
}

.launchpad-enter-active,
.launchpad-leave-active {
  transition: opacity 0.22s ease;
}

.launchpad-enter-from,
.launchpad-leave-to {
  opacity: 0;
}

@media (max-width: 560px) {
  .workspace-grid {
    background-size: 36px 36px;
  }
}
</style>
