<script setup lang="ts">
/**
 * # 桌面状态栏
 *
 * 顶部系统栏，三栏布局：
 * - **左侧**：用户标识（`privilegeClass:currentUser`，来自 desktopStore）
 * - **中间**：实时时钟
 * - **右侧**：系统状态菜单（网络、声音、电源）
 *
 * ## 菜单管理模式
 *
 * 使用 `activeMenuId` 单例模式，同一时间只有一个菜单展开。
 * 点击同一菜单的触发按钮会关闭它，点击不同菜单会切换。
 * 点击菜单外部区域（通过 StatusMenuButton 的 click-outside 检测）也会关闭。
 *
 * ## 事件转发
 *
 * NetworkMenu 的 `@action` 事件通过 emit 转发给 DesktopView：
 * `NetworkMenu → @action → handleNetworkAction → emit('networkAction') → DesktopView`
 *
 * SoundMenu 和 PowerMenu 通过 Pinia Store 直接操作状态，不需要转发。
 */

import { ref } from 'vue'
import { Power, Volume2, Wifi } from 'lucide-vue-next'

import NetworkMenu from './status/NetworkMenu.vue'
import PowerMenu from './status/PowerMenu.vue'
import SoundMenu from './status/SoundMenu.vue'
import StatusMenuButton from './status/StatusMenuButton.vue'
import TokenBalance from './status/TokenBalance.vue'
import { useDesktopStore } from '@/stores/desktop'

defineProps<{
  time: string
}>()

const emit = defineEmits<{
  networkAction: [action: 'disconnect' | 'edit-ip' | 'edit-dns']
  switchUser: []
  restart: []
  shutdown: []
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

function handleSwitchUser() {
  setActiveMenu(null)
  emit('switchUser')
}

function handleRestart() {
  setActiveMenu(null)
  emit('restart')
}

function handleShutdown() {
  setActiveMenu(null)
  emit('shutdown')
}
</script>

<template>
  <header class="status-bar">
    <div class="status-bar__user">
      <span class="status-bar__identity">
        {{ desktop.privilegeClass }}:{{ desktop.currentUser }}
      </span>
      <TokenBalance />
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
        <PowerMenu
          :on-switch-user="handleSwitchUser"
          :on-restart="handleRestart"
          :on-shutdown="handleShutdown"
        />
      </StatusMenuButton>
    </div>
  </header>
</template>

<style scoped>
.status-bar {
  position: relative;
  z-index: 1000;
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

.status-bar__user {
  gap: 10px;
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
