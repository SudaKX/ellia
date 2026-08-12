<script setup lang="ts">
/**
 * # LoginView — 登录 / 注册
 *
 * 出题器入口页。首个注册账号自动成为管理员。
 */

import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const error = ref<string | null>(null)

function switchMode(next: 'login' | 'register') {
  mode.value = next
  error.value = null
}

async function handleSubmit() {
  error.value = null
  const result =
    mode.value === 'login'
      ? await auth.login(username.value, password.value)
      : await auth.register(username.value, password.value)
  if (!result.ok) {
    error.value = result.error ?? '操作失败'
    return
  }
  router.replace('/questions')
}
</script>

<template>
  <div class="login">
    <div class="login__panel">
      <p class="login__eyebrow">PUZZLE DESIGNER</p>
      <h1 class="login__title">出题器</h1>

      <div class="login__tabs">
        <button
          class="login__tab login__tab--active"
          type="button"
          @click="switchMode('login')"
        >
          登录
        </button>
        <!-- 注册入口已停用：账号由服务端预置（server/src/seed-users.js），
             需要新账号请管理员在服务端添加 -->
        <!-- <button
          class="login__tab"
          :class="{ 'login__tab--active': mode === 'register' }"
          type="button"
          @click="switchMode('register')"
        >
          注册
        </button> -->
      </div>

      <form class="login__form" @submit.prevent="handleSubmit">
        <label class="login__field">
          <span class="login__label">用户名</span>
          <input
            v-model="username"
            class="login__input"
            type="text"
            autocomplete="username"
            required
          />
        </label>
        <label class="login__field">
          <span class="login__label">密码</span>
          <input
            v-model="password"
            class="login__input"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>

        <p v-if="error" class="login__error">{{ error }}</p>
        <!-- 注册提示已停用（见上方注册 tab 注释） -->
        <!-- <p v-if="mode === 'register'" class="login__hint">
          首个注册的账号自动成为管理员，其余为普通出题者。
        </p> -->

        <button class="login__submit" type="submit">
          {{ mode === 'login' ? '登录' : '注册并登录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login {
  display: grid;
  min-height: 100%;
  place-items: center;
  padding: 24px;
}

.login__panel {
  width: 100%;
  max-width: 380px;
  padding: 28px;
  border: 1px solid var(--line-default);
  background: var(--surface-raised);
  box-shadow: 0 18px 56px rgba(0, 0, 0, 0.45);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.login__eyebrow {
  margin: 0;
  color: var(--signal-red-soft);
  font: 700 10px var(--font-mono);
  letter-spacing: 0.2em;
}

.login__title {
  margin: 0;
  color: var(--text-primary);
  font: 700 22px var(--font-mono);
}

.login__tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--line-subtle);
}

.login__tab {
  padding: 8px 14px;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  background: transparent;
  font: 12px var(--font-ui);
  cursor: pointer;
  transition: color 0.12s, border-color 0.12s;
}

.login__tab--active {
  color: var(--text-primary);
  border-bottom-color: var(--signal-red-soft);
}

.login__form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.login__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.login__label {
  color: var(--text-muted);
  font: 11px var(--font-ui);
}

.login__input {
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: var(--surface-panel);
  font: 13px var(--font-mono);
  outline: none;
  transition: border-color 0.12s;
}

.login__input:focus {
  border-color: var(--signal-red-soft);
}

.login__error {
  margin: 0;
  color: var(--signal-red);
  font: 12px var(--font-ui);
}

.login__hint {
  margin: 0;
  color: var(--text-muted);
  font: 11px/1.6 var(--font-ui);
}

.login__submit {
  min-height: 36px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: var(--surface-panel);
  font: 600 12px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s;
}

.login__submit:hover {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}
</style>
