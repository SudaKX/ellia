import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as authApi from '../api/auth'
import { ApiClientError } from '../api/client'
import type { AuthUser, LoginInput, RegisterInput } from '../api/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const initialized = ref(false)

  const isAdmin = computed(() => user.value?.role === 'admin')

  async function fetchMe(): Promise<void> {
    try {
      const response = await authApi.me()
      user.value = response.user
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 401) {
        user.value = null
        return
      }
      throw error
    }
  }

  /** 应用挂载前调用：401 视为匿名，网络故障不阻断页面渲染。 */
  async function initialize(): Promise<void> {
    try {
      await fetchMe()
    } catch (error) {
      console.error('[auth] initialize failed:', error)
      user.value = null
    } finally {
      initialized.value = true
    }
  }

  async function login(input: LoginInput): Promise<void> {
    const response = await authApi.login(input)
    user.value = response.user
  }

  async function register(input: RegisterInput): Promise<void> {
    const response = await authApi.register(input)
    user.value = response.user
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } finally {
      user.value = null
    }
  }

  return { user, initialized, isAdmin, initialize, fetchMe, login, register, logout }
})
