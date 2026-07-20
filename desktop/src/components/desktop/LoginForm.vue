<script setup lang="ts">
/**
 * # 登录表单
 *
 * FakeOS 的登录表单组件，通过 WindowFrame 组件嵌入到登录页面中。
 * 提供两种登录方式：密码登录和密钥（Token）登录。
 *
 * ## 事件传递
 *
 * 由于 WindowFrame 通过 `<component :is>` 动态渲染且只转发 `@close` 事件，
 * 本组件通过 `onLogin` / `onTokenLogin` prop（由父组件通过 `componentProps` 传入）
 * 回调，避免在 WindowFrame 上层额外转发事件。
 *
 * ## 使用方式
 *
 * ```ts
 * componentProps: {
 *   onLogin: (user, pass) => router.push('/'),
 *   onTokenLogin: () => router.push('/'),
 * }
 * ```
 */

import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { KeyRound, LogIn } from 'lucide-vue-next'

const props = defineProps<{
  /** 密码登录回调：用户点击"登录"或按 Enter */
  onLogin?: (username: string, password: string) => void
  /** 密钥登录回调：基于浏览器存储的 token 自动登录（TODO: 尚未实现 token 检测） */
  onTokenLogin?: () => void
}>()

const { t } = useI18n({ useScope: 'global' })

const username = ref('')
const password = ref('')
const error = ref('')

function handleSubmit() {
  if (!username.value.trim()) {
    error.value = t('login.errorUsername')
    return
  }
  if (!password.value.trim()) {
    error.value = t('login.errorPassword')
    return
  }
  error.value = ''
  props.onLogin?.(username.value.trim(), password.value)
}

/** 密钥登录：当前仅转发回调，token 检测逻辑待后端接入后实现。 */
function handleTokenLogin() {
  props.onTokenLogin?.()
}
</script>

<template>
  <form class="login-form" @submit.prevent="handleSubmit">
    <label class="login-form__field">
      <span class="login-form__label">{{ t('login.username') }}</span>
      <input
        v-model="username"
        class="login-form__input"
        type="text"
        autocomplete="username"
        :placeholder="t('login.usernamePlaceholder')"
      />
    </label>

    <label class="login-form__field">
      <span class="login-form__label">{{ t('login.password') }}</span>
      <input
        v-model="password"
        class="login-form__input"
        type="password"
        autocomplete="current-password"
        :placeholder="t('login.passwordPlaceholder')"
      />
    </label>

    <p v-if="error" class="login-form__error">{{ error }}</p>

    <div class="login-form__actions">
      <button class="login-form__submit" type="submit">
        <LogIn :size="14" :stroke-width="1.8" />
        <span>{{ t('login.submit') }}</span>
      </button>
      <button
        class="login-form__submit login-form__submit--token"
        type="button"
        @click="handleTokenLogin"
      >
        <KeyRound :size="14" :stroke-width="1.8" />
        <span>{{ t('login.tokenSubmit') }}</span>
      </button>
    </div>
  </form>
</template>

<style scoped>
.login-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  min-height: 0;
}

.login-form__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.login-form__label {
  color: var(--text-secondary);
  font: 600 11px var(--font-ui);
}

.login-form__input {
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: var(--surface-panel);
  font: 12px var(--font-mono);
  outline: none;
  transition: border-color 0.12s;
}

.login-form__input:focus {
  border-color: var(--signal-red-soft);
}

.login-form__input::placeholder {
  color: var(--text-muted);
}

.login-form__error {
  margin: 0;
  color: var(--signal-red);
  font: 11px var(--font-ui);
}

.login-form__actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.login-form__submit {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 34px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: transparent;
  font: 600 12px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.login-form__submit:hover {
  border-color: var(--signal-mint);
  color: var(--signal-mint);
  background: var(--surface-hover);
}

.login-form__submit--token {
  color: var(--text-muted);
}

.login-form__submit--token:hover {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
  background: var(--surface-hover);
}
</style>
