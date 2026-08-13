/**
 * # 代币余额 Store
 *
 * 单一数据源：状态栏钱包胶囊、谜题消费、成就奖励都从这里读取。
 * - 真实 API：`GET /api/v1/credits` → `{ vtb, version }`（响应带 no-store）
 * - Mock 模式：`USE_REAL_API=false` 时使用本地演示余额，行为与真实 API 一致
 *
 * 后端加入自定义代币时，扩展 `TokenBalances` 字段即可，
 * 展示层按 kind 渲染，无需改动 UI 结构。
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { useAuth } from '@/composables/useAuth'
import { CREDITS_ENDPOINTS, USE_REAL_API } from '@/config/api'

/** 各代币余额（当前仅有 vtb；后端扩展时在此追加字段） */
export interface TokenBalances {
  vtb: number
}

/** Mock 模式演示余额；接入真实后端后自动被 API 数据覆盖 */
const MOCK_VTB_BALANCE = 128

export const useCreditsStore = defineStore('credits', () => {
  const balances = ref<TokenBalances>({ vtb: 0 })
  /** 后端乐观锁版本号，支付/变更后可做冲突检测 */
  const version = ref(0)
  const isLoading = ref(false)
  const isLoaded = ref(false)
  const error = ref<string | null>(null)

  const vtb = computed(() => balances.value.vtb)

  /** 拉取代币余额；真实 API 失败时保留上次数据并记录 error */
  async function fetchBalances(): Promise<void> {
    isLoading.value = true
    error.value = null

    if (USE_REAL_API) {
      try {
        const auth = useAuth()
        const token = auth.getToken()
        const res = await fetch(CREDITS_ENDPOINTS.balances, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        })
        if (!res.ok) throw new Error(`credits request failed: ${res.status}`)
        const data = (await res.json()) as { vtb?: number; version?: number }
        balances.value = { vtb: data.vtb ?? 0 }
        version.value = data.version ?? 0
        isLoaded.value = true
      } catch (cause) {
        error.value = cause instanceof Error ? cause.message : String(cause)
      } finally {
        isLoading.value = false
      }
      return
    }

    // Mock 模式：与真实 API 的数据形态保持一致
    balances.value = { vtb: MOCK_VTB_BALANCE }
    version.value = 0
    isLoaded.value = true
    isLoading.value = false
  }

  /** 登出/切换账号时清空余额 */
  function reset(): void {
    balances.value = { vtb: 0 }
    version.value = 0
    isLoading.value = false
    isLoaded.value = false
    error.value = null
  }

  return { balances, version, vtb, isLoading, isLoaded, error, fetchBalances, reset }
})
