<script setup lang="ts">
import { useRouter } from 'vue-router'

import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'

const auth = useAuthStore()
const theme = useThemeStore()
const router = useRouter()

async function onLogout(): Promise<void> {
  await auth.logout()
  await router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <header class="app-bar">
      <RouterLink class="app-bar__brand" to="/">Ellia Puzzle Editor</RouterLink>

      <nav class="app-nav" aria-label="主导航">
        <RouterLink v-if="auth.user" class="nav-link" to="/">项目</RouterLink>
        <RouterLink v-if="auth.isAdmin" class="nav-link" to="/admin">管理</RouterLink>
        <RouterLink v-if="!auth.user" class="nav-link" to="/login">登录</RouterLink>
        <RouterLink v-if="!auth.user" class="nav-link" to="/register">注册</RouterLink>
      </nav>

      <div class="app-bar__spacer"></div>

      <span v-if="auth.user" class="app-bar__user">
        {{ auth.user.username }} · {{ auth.user.role }}
      </span>

      <button
        class="icon-button"
        type="button"
        :aria-label="theme.mode === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
        :title="theme.mode === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
        @click="theme.toggle()"
      >
        {{ theme.mode === 'dark' ? '☀️' : '🌙' }}
      </button>

      <button v-if="auth.user" class="btn btn--text btn--small" type="button" @click="onLogout">
        登出
      </button>
    </header>

    <RouterView />
  </div>
</template>
