<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import { safeRedirect } from '../utils/redirect'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const errorMessage = ref('')
const submitting = ref(false)

async function onSubmit(): Promise<void> {
  errorMessage.value = ''
  submitting.value = true
  try {
    await auth.login({ username: username.value, password: password.value })
    await router.push(safeRedirect(route.query.redirect))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登录失败，请重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="card auth-card" aria-labelledby="login-title">
      <header>
        <h1 id="login-title">登录</h1>
        <p class="muted">使用 Ellia Puzzle Editor 账号继续</p>
      </header>

      <form novalidate @submit.prevent="onSubmit">
        <div class="field">
          <label for="login-username">用户名</label>
          <input
            id="login-username"
            v-model="username"
            name="username"
            type="text"
            autocomplete="username"
            required
            autofocus
          >
        </div>

        <div class="field">
          <label for="login-password">密码</label>
          <input
            id="login-password"
            v-model="password"
            name="password"
            type="password"
            autocomplete="current-password"
            required
          >
        </div>

        <p v-if="errorMessage" class="alert alert--error" role="alert">{{ errorMessage }}</p>

        <div class="form-actions">
          <button class="btn btn--primary" type="submit" :disabled="submitting">
            {{ submitting ? '登录中…' : '登录' }}
          </button>
          <RouterLink class="btn btn--text" to="/register">没有账号？注册</RouterLink>
        </div>
      </form>
    </section>
  </main>
</template>
