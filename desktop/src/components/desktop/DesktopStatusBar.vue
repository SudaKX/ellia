<script setup lang="ts">
import { ref } from 'vue'
import { Power, Volume2, Wifi } from 'lucide-vue-next'

import NetworkMenu from './status/NetworkMenu.vue'
import PowerMenu from './status/PowerMenu.vue'
import SoundMenu from './status/SoundMenu.vue'
import StatusMenuButton from './status/StatusMenuButton.vue'
import { useDesktopStore } from '@/stores/desktop'

defineProps<{
  time: string
}>()

const emit = defineEmits<{
  networkAction: [action: 'disconnect' | 'edit-ip' | 'edit-dns']
}>()

const desktop = useDesktopStore()
const activeMenuId = ref<string | null>(null)

function setActiveMenu(menuId: string | null) {
  activeMenuId.value = menuId
}

function handleNetworkAction(action: 'disconnect' | 'edit-ip' | 'edit-dns') {
  setActiveMenu(null)
  emit('networkAction', action)
}
</script>

<template>
  <header class="status-bar">
    <div class="status-bar__user">
      <span class="status-bar__identity">
        {{ desktop.privilegeClass }}:{{ desktop.currentUser }}
      </span>
    </div>

    <div class="status-bar__time">
      <time :datetime="time">{{ time }}</time>
    </div>

    <div class="status-bar__system">
      <StatusMenuButton
        menu-id="network"
        label="Network"
        :icon="Wifi"
        :active-menu-id="activeMenuId"
        @set-active="setActiveMenu"
      >
        <NetworkMenu @action="handleNetworkAction" />
      </StatusMenuButton>
      <StatusMenuButton
        menu-id="sound"
        label="Sound"
        :icon="Volume2"
        :active-menu-id="activeMenuId"
        @set-active="setActiveMenu"
      >
        <SoundMenu />
      </StatusMenuButton>
      <StatusMenuButton
        menu-id="power"
        label="Power"
        :icon="Power"
        :active-menu-id="activeMenuId"
        @set-active="setActiveMenu"
      >
        <PowerMenu />
      </StatusMenuButton>
    </div>
  </header>
</template>

<style scoped>
.status-bar {
  position: relative;
  z-index: 20;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  min-height: 40px;
  padding: 0 18px;
  border-bottom: 1px solid var(--line-subtle);
  background: var(--surface-raised);
}

.status-bar__user,
.status-bar__system,
.status-bar__time {
  display: flex;
  align-items: center;
}

.status-bar__identity {
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
}

.status-bar__time {
  justify-content: center;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 12px;
}

.status-bar__system {
  justify-content: flex-end;
  gap: 6px;
}

@media (max-width: 680px) {
  .status-bar {
    padding: 0 12px;
  }
}
</style>
