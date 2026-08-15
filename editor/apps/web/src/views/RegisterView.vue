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
const inviteCode = ref('')
const errorMessage = ref('')
const submitting = ref(false)

async function onSubmit(): Promise<void> {
  errorMessage.value = ''
  submitting.value = true
  try {
    await auth.register({
      username: username.value,
      password: password.value,
      invite_code: inviteCode.value,
    })
    await router.push(safeRedirect(route.query.redirect))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '注册失败，请重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="card auth-card" aria-labelledby="register-title">
      <header>
        <h1 id="register-title">注册</h1>
        <p class="muted">注册需要一个管理员发放的一次性邀请码</p>
      </header>

      <form novalidate @submit.prevent="onSubmit">
        <div class="field">
          <label for="register-username">用户名</label>
          <input
            id="register-username"
            v-model="username"
            name="username"
            type="text"
            autocomplete="username"
            required
          >
          <p class="hint">3-32 位字母、数字、_ 或 -</p>
        </div>

        <div class="field">
          <label for="register-password">密码</label>
          <input
            id="register-password"
            v-model="password"
            name="password"
            type="password"
            autocomplete="new-password"
            required
          >
          <p class="hint">8-128 个字符</p>
        </div>

        <div class="field">
          <label for="register-invite">邀请码</label>
          <input
            id="register-invite"
            v-model="inviteCode"
            name="invite_code"
            type="text"
            autocomplete="off"
            spellcheck="false"
            required
          >
        </div>

        <p v-if="errorMessage" class="alert alert--error" role="alert">{{ errorMessage }}</p>

        <div class="form-actions">
          <button class="btn btn--primary" type="submit" :disabled="submitting">
            {{ submitting ? '注册中…' : '注册' }}
          </button>
          <RouterLink class="btn btn--text" to="/login">已有账号？登录</RouterLink>
        </div>
      </form>
    </section>
  </main>
</template>
