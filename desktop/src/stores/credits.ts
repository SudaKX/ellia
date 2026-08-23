/**
 * # 代币余额 Store
 *
 * 单一数据源：状态栏钱包胶囊、谜题消费、成就奖励都从这里读取。
 * - 真实 API：`GET /api/v1/credits`（Bearer）→ `{ vtb, version }`（响应带 no-store）
 * - Mock 模式：`USE_REAL_API=false` 时使用本地余额，行为与真实 API 一致
 *
 * ## 本地持久化
 *
 * 余额写入 localStorage（`ellia.credits.vtb`），刷新/重新登录后自动恢复；
 * 浏览器彩蛋等本地奖励通过 `grantVtb()` 发放并立即落盘。
 * 真实 API 模式下本地值仅作启动暂显，成功拉取后以服务端数据为准。
 *
 * ## 后端增减端点缺失说明（重要）
 *
 * 后端 `GET /api/v1/credits` 只读余额，**没有发放/消费端点**——
 * 服务端 VTB 由后端业务驱动（消费提示扣费、成就奖励结算等）。
 * 因此真实模式下 `grantVtb()` / `spendVtb()` 只改本地展示，刷新后以服务端为准。
 * 若需本地彩蛋奖励持久化，需后端补发放端点后再接入（见 `docs/backend-integration.md`）。
 *
 * 后端加入自定义代币时，扩展 `TokenBalances` 字段即可，
 * 展示层按 kind 渲染，无需改动 UI 结构。
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { CREDITS_ENDPOINTS, USE_REAL_API } from '@/config/api'
import { apiFetch } from '@/utils/http'

/** 各代币余额（当前仅有 vtb；后端扩展时在此追加字段） */
export interface TokenBalances {
  vtb: number
}

/** Mock 模式初始余额（本地从未保存过数据时使用） */
const MOCK_VTB_BALANCE = 128

/** 本地持久化 key：VTB 余额 */
const VTB_STORAGE_KEY = 'ellia.credits.vtb'

/** 读取本地保存的 VTB 余额；无数据或数据非法时返回 null */
function readStoredVtb(): number | null {
  if (typeof window === 'undefined') return null
  const raw = window.localStorage.getItem(VTB_STORAGE_KEY)
  if (raw === null) return null
  const value = Number(raw)
  return Number.isFinite(value) && value >= 0 ? Math.floor(value) : null
}

/** 写入本地 VTB 余额 */
function writeStoredVtb(value: number): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(VTB_STORAGE_KEY, String(value))
}

export const useCreditsStore = defineStore('credits', () => {
  const balances = ref<TokenBalances>({ vtb: readStoredVtb() ?? MOCK_VTB_BALANCE })
  /** 后端乐观锁版本号，支付/变更后可做冲突检测 */
  const version = ref(0)
  const isLoading = ref(false)
  /** 本地已有数据时立即可用，无需等待网络 */
  const isLoaded = ref(true)
  const error = ref<string | null>(null)
  /** 最近一次余额变化的增量（正=入账，负=支出；null=无变化） */
  const lastDelta = ref<number | null>(null)
  /** 余额变化动画触发序号，每次变化 +1 */
  const changeSequence = ref(0)

  const vtb = computed(() => balances.value.vtb)

  /** 拉取代币余额；真实 API 失败时保留上次数据并记录 error */
  async function fetchBalances(): Promise<void> {
    isLoading.value = true
    error.value = null

    if (USE_REAL_API) {
      try {
        // GET /api/v1/credits（apiFetch 自动带 Bearer + ProblemDetails 解析）
        // 响应 `{vtb, version}`；401 时可先 useAuth().refreshToken() 再重试
        const data = await apiFetch<{ vtb?: number; version?: number }>(CREDITS_ENDPOINTS.balances)
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

    // Mock 模式：优先恢复本地保存的余额
    balances.value = { vtb: readStoredVtb() ?? MOCK_VTB_BALANCE }
    version.value = 0
    isLoaded.value = true
    isLoading.value = false
  }

  /**
   * 本地发放 VTB（浏览器彩蛋/演示用），立即写入 localStorage 持久化。
   *
   * 注意：后端没有 /credits 增减端点（见文件头"后端增减端点缺失说明"），
   * 真实模式下本函数仅改本地展示，刷新后以服务端 GET /credits 为准。
   */
  function grantVtb(amount: number): number {
    if (!Number.isInteger(amount) || amount <= 0) {
      throw new Error('VTB grant amount must be a positive integer.')
    }
    balances.value = { vtb: balances.value.vtb + amount }
    version.value += 1
    isLoaded.value = true
    writeStoredVtb(balances.value.vtb)
    lastDelta.value = amount
    changeSequence.value += 1
    return balances.value.vtb
  }

  /**
   * 消费 VTB（如 AI 帮开提示扣费）。
   * 余额不足时返回 false，不产生任何变化。
   *
   * 注意：真实模式下仅本地扣减展示；服务端扣费应走后端业务端点
   * （如 `POST /api/v1/hints/{hint_id}/disclose` 由后端扣减后重新拉取余额）。
   */
  function spendVtb(amount: number): boolean {
    if (!Number.isInteger(amount) || amount <= 0) {
      throw new Error('VTB spend amount must be a positive integer.')
    }
    if (balances.value.vtb < amount) return false
    balances.value = { vtb: balances.value.vtb - amount }
    version.value += 1
    isLoaded.value = true
    writeStoredVtb(balances.value.vtb)
    lastDelta.value = -amount
    changeSequence.value += 1
    return true
  }

  /** 登出/切换账号时清空内存余额（本地保存保留，重新登录后恢复） */
  function reset(): void {
    balances.value = { vtb: readStoredVtb() ?? 0 }
    version.value = 0
    isLoading.value = false
    isLoaded.value = true
    error.value = null
    lastDelta.value = null
    changeSequence.value = 0
  }

  return {
    balances,
    version,
    vtb,
    isLoading,
    isLoaded,
    error,
    lastDelta,
    changeSequence,
    fetchBalances,
    grantVtb,
    spendVtb,
    reset,
  }
})
