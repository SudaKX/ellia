/**
 * # App.vue — 出题器根组件
 *
 * 仅渲染路由出口 + 全局外壳（顶栏品牌 + 主题切换 + 当前登录用户 + 退出）。
 */

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { THEMES, currentTheme, setTheme, type Theme } from '@/composables/useTheme'

const auth = useAuthStore()
const router = useRouter()

function handleLogout() {
  auth.logout()
  router.replace('/login')
}

// ─── 主题切换 ──────────────────────────────────────

const themeOpen = ref(false)
const theme = ref<Theme>(currentTheme())

function selectTheme(key: Theme) {
  theme.value = key
  setTheme(key)
  themeOpen.value = false
}
</script>

<template>
  <div class="app">
    <header class="app__bar">
      <span class="app__brand">出题器 <small>PUZZLE DESIGNER</small></span>

      <div class="app__theme">
        <button class="app__theme-btn" type="button" @click="themeOpen = !themeOpen">
          <span class="app__theme-swatch" :data-theme-preview="theme"></span>
          {{ THEMES.find((item) => item.key === theme)?.label }}
        </button>
        <div v-if="themeOpen" class="app__theme-menu">
          <button
            v-for="item in THEMES"
            :key="item.key"
            class="app__theme-item"
            :class="{ 'app__theme-item--active': item.key === theme }"
            type="button"
            @click="selectTheme(item.key)"
          >
            <span class="app__theme-swatch" :data-theme-preview="item.key"></span>
            {{ item.label }}
          </button>
        </div>
      </div>

      <span v-if="auth.currentUser" class="app__user">
        {{ auth.currentUser?.role === 'admin' ? '管理员' : '出题者' }} · {{ auth.currentUser?.username }}
        <button class="app__logout" type="button" @click="handleLogout">退出</button>
      </span>
    </header>
    <main class="app__main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--canvas);
}

.app__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  height: 40px;
  padding: 0 14px;
  border-bottom: 1px solid var(--line-subtle);
  background: var(--surface-raised);
}

.app__brand {
  color: var(--signal-red-soft);
  font: 700 13px var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.app__brand small {
  color: var(--text-muted);
  font-weight: 400;
  font-size: 9px;
  letter-spacing: 0.18em;
}

.app__user {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary);
  font: 12px var(--font-ui);
}

/* ── 主题切换 ── */
.app__theme {
  position: relative;
  margin-left: auto;
  margin-right: 14px;
}

.app__theme-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 26px;
  padding: 0 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-secondary);
  background: transparent;
  font: 11px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s;
}

.app__theme-btn:hover {
  border-color: var(--signal-red-soft);
  color: var(--text-primary);
}

.app__theme-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 20;
  min-width: 132px;
  border: 1px solid var(--line-default);
  background: var(--surface-raised);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
  display: flex;
  flex-direction: column;
  padding: 4px;
}

.app__theme-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: none;
  color: var(--text-secondary);
  background: transparent;
  font: 12px var(--font-ui);
  text-align: left;
  cursor: pointer;
  transition: background-color 0.12s, color 0.12s;
}

.app__theme-item:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.app__theme-item--active {
  color: var(--signal-red-soft);
}

/* 主题色块预览（各主题的强调色） */
.app__theme-swatch {
  width: 10px;
  height: 10px;
  border: 1px solid var(--line-default);
  background: var(--signal-red-soft);
  flex-shrink: 0;
}

.app__theme-swatch[data-theme-preview="day"] {
  background: #d32f2f;
}

.app__theme-swatch[data-theme-preview="deep-blue"] {
  background: #64ffda;
}

.app__theme-swatch[data-theme-preview="parchment"] {
  background: #c0392b;
}

.app__theme-swatch[data-theme-preview="rose"] {
  background: #cd5076;
}

.app__logout {
  padding: 4px 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: transparent;
  font: 11px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s;
}

.app__logout:hover {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}

.app__main {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
</style>
