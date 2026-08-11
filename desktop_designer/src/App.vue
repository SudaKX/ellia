/**
 * # App.vue — 出题器根组件
 *
 * 仅渲染路由出口 + 全局外壳（顶栏品牌 + 当前登录用户 + 退出）。
 */

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

function handleLogout() {
  auth.logout()
  router.replace('/login')
}
</script>

<template>
  <div class="app">
    <header class="app__bar">
      <span class="app__brand">出题器 <small>PUZZLE DESIGNER</small></span>
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
