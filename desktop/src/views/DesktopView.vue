<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Archive, FileText, Info, LockKeyhole, TerminalSquare } from 'lucide-vue-next'

import DesktopStatusBar from '@/components/desktop/DesktopStatusBar.vue'
import DockBar from '@/components/desktop/DockBar.vue'
import type { DockApplicationState } from '@/components/desktop/DockBar.vue'
import Launchpad from '@/components/desktop/Launchpad.vue'
import MessageBox from '@/components/desktop/MessageBox.vue'
import PermissionDenied from '@/components/desktop/PermissionDenied.vue'
import WindowFrame from '@/components/desktop/WindowFrame.vue'
import FileExplorer from '@/components/applications/FileExplorer.vue'
import ArchiveViewer from '@/components/applications/ArchiveViewer.vue'
import Terminal from '@/components/applications/Terminal.vue'
import SandboxControl from '@/components/applications/SandboxControl.vue'
import { useFilterService } from '@/composables/useFilterService'
import type { GlitchOptions } from '@/composables/useGlitchFilter'
import { useWindowService } from '@/composables/useWindowService'
import type { FilterType } from '@/filters'
import { useDesktopStore } from '@/stores/desktop'
import type { ApplicationId } from '@/types/desktop'

const desktop = useDesktopStore()
const windowService = useWindowService()
const filterService = useFilterService()
const windowGlitchOptions: GlitchOptions = {
  intensity: 12,
  frequencyX: 0.002,
  frequencyY: 0.05,
  enableHorizontalDisplacement: true,
  enableVerticalDisplacement: false,
  chromaticAberration: 0.002,
  animate: true,
  frameSkip: 8,
}
const windowGlitchFilter = filterService.create('glitch', windowGlitchOptions)
const windowFilterIds: Partial<Record<FilterType, string>> = {
  glitch: windowGlitchFilter.filterId,
}

const applicationRegistry: Record<ApplicationId, { title: string }> = {
  files: { title: 'File Explorer' },
  archive: { title: 'Archive Viewer' },
  terminal: { title: 'Command Terminal' },
  sandbox: { title: 'Sandbox Control' },
}

type NetworkAction = 'disconnect' | 'edit-ip' | 'edit-dns'

const networkMessages: Record<NetworkAction, { title: string }> = {
  disconnect: {
    title: 'Disconnect network',
  },
  'edit-ip': {
    title: 'IP assignment',
  },
  'edit-dns': {
    title: 'DNS server assignment',
  },
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

function handleNetworkAction(action: NetworkAction) {
  const message = networkMessages[action]

  windowService.send({
    type: 'create-window',
    payload: {
      title: message.title,
      icon: Info,
      component: MessageBox,
      componentProps: {
        contentComponent: PermissionDenied,
      },
      defaultWidth: 440,
      defaultHeight: 220,
      placement: 'center',
      mode: 'modal',
      resizable: false,
      filters: {
        glitch: true,
      },
      controls: {
        minimize: false,
        close: true,
      },
    },
  })
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
  filterService.destroy(windowGlitchFilter.instanceId)
})
</script>

<template>
  <main class="desktop-shell">
    <DesktopStatusBar :time="time" @network-action="handleNetworkAction" />

    <section class="desktop-workspace" aria-label="FakeOS desktop workspace">
      <div class="workspace-grid" aria-hidden="true"></div>

      <WindowFrame
        v-for="window in windowService.windows.value"
        :key="window.id"
        :window="window"
        :is-active="windowService.activeWindowId.value === window.id"
        :filter-ids="windowFilterIds"
        @close="windowService.send({ type: 'close-window', windowId: window.id })"
        @focus="windowService.send({ type: 'focus-window', windowId: window.id })"
        @minimize="windowService.send({ type: 'minimize-window', windowId: window.id })"
      />
    </section>

    <Transition name="modal-overlay">
      <div v-if="windowService.hasModalWindow.value" class="desktop-modal-overlay" aria-hidden="true"></div>
    </Transition>

    <Transition name="launchpad">
      <Launchpad
        v-if="desktop.isApplicationOverviewOpen"
        :applications="desktop.applications"
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

.desktop-modal-overlay {
  position: fixed;
  z-index: 1100;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  background: rgb(0 0 0 / 54%);
}

.modal-overlay-enter-active,
.modal-overlay-leave-active {
  transition: opacity 0.18s ease;
}

.modal-overlay-enter-from,
.modal-overlay-leave-to {
  opacity: 0;
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
