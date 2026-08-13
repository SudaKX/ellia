<script setup lang="ts">
import { Power, UserRound, RotateCw, PowerOff } from 'lucide-vue-next'

/**
 * 电源 / 会话控制菜单。
 *
 * 通过 props 回调处理点击事件（避免 slot 环境下 emit 传递不可靠的问题）：
 * - `onSwitchUser` — 切换登录账户
 * - `onRestart`    — 重启 FakeOS 会话
 * - `onShutdown`   — 关闭 / 退出
 *
 * 关机按钮以红色标注并与其他项用分隔线隔开，防止误触。
 *
 * 同时保留 emit 兼容 LoginView 中无 prop 回调的场景。
 */
const props = defineProps<{
  /** 切换登录账户回调 */
  onSwitchUser?: () => void
  /** 重启回调 */
  onRestart?: () => void
  /** 关机回调 */
  onShutdown?: () => void
}>()

defineEmits<{
  switchUser: []
  restart: []
  shutdown: []
}>()
</script>

<template>
  <div class="power-menu">
    <div class="menu-header">
      <Power :size="14" :stroke-width="1.8" />
      <span class="menu-title">Power</span>
    </div>
    <div class="menu-body">
      <button class="menu-item" @click="onSwitchUser ? onSwitchUser() : $emit('switchUser')">
        <UserRound :size="14" :stroke-width="1.5" />
        <span>更改账户</span>
      </button>
      <button class="menu-item" @click="onRestart ? onRestart() : $emit('restart')">
        <RotateCw :size="14" :stroke-width="1.5" />
        <span>重启</span>
      </button>
      <button class="menu-item menu-item--danger" @click="onShutdown ? onShutdown() : $emit('shutdown')">
        <PowerOff :size="14" :stroke-width="1.5" />
        <span>关机</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.power-menu {
  padding: 12px;
}

.menu-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-subtle);
  color: var(--text-secondary);
}

.menu-title {
  color: var(--text-primary);
  font: 600 12px var(--font-ui);
}

.menu-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  border: none;
  border-radius: 0;
  color: var(--text-secondary);
  background: transparent;
  font: 12px var(--font-ui);
  transition: color 0.12s, background-color 0.12s;
}

.menu-item:hover {
  color: var(--text-primary);
  background: var(--surface-hover);
}

.menu-item--danger {
  margin-top: 4px;
  padding-top: 10px;
  border-top: 1px solid var(--line-subtle);
  color: var(--signal-red-soft);
}

.menu-item--danger:hover {
  color: var(--signal-red);
  background: var(--surface-hover);
}
</style>
