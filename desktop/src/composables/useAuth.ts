/**
 * # 鉴权状态管理
 *
 * 基于 localStorage 的 Token 鉴权系统，支持玩家账户和管理员账户两套登录态。
 *
 * ## 账户体系
 *
 * - `player`：普通玩家账户（用户自行命名的虚拟身份，底层账户唯一）
 * - `admin`：JDK 触发器管理员账户
 * - 两套账户的登录态独立存储，互不干扰
 *
 * ## localStorage 存储键
 *
 * | 键                     | 内容               | 说明                  |
 * |------------------------|-------------------|----------------------|
 * | `ell_auth_token`       | JWT / session token | 当前活跃的认证令牌       |
 * | `ell_player_logged_in` | `"true"` / 不存在   | 玩家账户是否已登录       |
 * | `ell_admin_logged_in`  | `"true"` / 不存在   | 管理员账户是否已登录     |
 *
 * ## 安全策略
 *
 * localStorage 不可信，每次进入登录页面时调用 `validateWithBackend()`
 * 向后端校验 token 有效性。后端未就绪时使用 mock 逻辑。
 *
 * ## 使用示例
 *
 * ```ts
 * import { useAuth } from '@/composables/useAuth'
 * const auth = useAuth()
 * auth.login('player', 'token', 'Alice')
 * auth.login('admin', 'admin_token')
 * await auth.validateWithBackend()  // 进入登录页时校验
 * ```
 */

import { computed, ref } from 'vue'
import { useDesktopStore } from '@/stores/desktop'

const TOKEN_KEY = 'ell_auth_token'
const PLAYER_KEY = 'ell_player_logged_in'
const ADMIN_KEY = 'ell_admin_logged_in'

/** 账户类型 */
export type AccountType = 'player' | 'admin'

/** 单例实例 */
let _instance: ReturnType<typeof createAuth> | null = null

function createAuth() {
  const token = ref<string | null>(null)
  const accountType = ref<AccountType | null>(null)
  const username = ref<string | null>(null)

  /** 是否已通过鉴权（任一账户类型登录即视为已认证） */
  const isAuthenticated = computed(() => token.value !== null && token.value.length > 0)

  /** 是否为管理员账户 */
  const isAdmin = computed(() => accountType.value === 'admin')

  /** 从 localStorage 恢复登录态 */
  function checkAuth(): boolean {
    const savedToken = localStorage.getItem(TOKEN_KEY)
    const isPlayer = localStorage.getItem(PLAYER_KEY) === 'true'
    const isAdminLogin = localStorage.getItem(ADMIN_KEY) === 'true'

    if (savedToken && savedToken.length > 0) {
      token.value = savedToken
      accountType.value = isAdminLogin ? 'admin' : isPlayer ? 'player' : null
      return true
    }
    return false
  }

  /** 登录：存储 token 并同步账户类型 */
  function login(type: AccountType, authToken: string, user: string = 'PLAYER'): void {
    token.value = authToken
    accountType.value = type
    username.value = user

    localStorage.setItem(TOKEN_KEY, authToken)

    if (type === 'admin') {
      localStorage.setItem(ADMIN_KEY, 'true')
      localStorage.removeItem(PLAYER_KEY)
    } else {
      localStorage.setItem(PLAYER_KEY, 'true')
      localStorage.removeItem(ADMIN_KEY)
    }

    // 同步到 desktopStore
    const desktop = useDesktopStore()
    desktop.currentUser = user
    desktop.accountType = type
  }

  /** 退出登录：清除所有认证状态 */
  function logout(): void {
    token.value = null
    accountType.value = null
    username.value = null

    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(PLAYER_KEY)
    localStorage.removeItem(ADMIN_KEY)
  }

  /** 是否有玩家账户登录 */
  const isPlayerLoggedIn = computed(() =>
    accountType.value === 'player' && isAuthenticated.value,
  )

  /** 是否有管理员账户登录 */
  const isAdminLoggedIn = computed(() =>
    accountType.value === 'admin' && isAuthenticated.value,
  )

  /**
   * 后端校验：进入登录页时调用，验证 localStorage 中的 token 是否仍然有效。
   *
   * TODO: 后端就绪后替换为 `POST /api/auth/validate`，返回 `{ valid: boolean, accountType?: string }`
   */
  async function validateWithBackend(): Promise<boolean> {
    const savedToken = localStorage.getItem(TOKEN_KEY)

    if (!savedToken) {
      logout()
      return false
    }

    // TODO: 替换为真实 API 调用
    // const res = await fetch('/api/auth/validate', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({ token: savedToken }),
    // })
    // if (!res.ok) { logout(); return false }
    // const data = await res.json()
    // return data.valid

    // Mock：本地 token 存在即认为有效
    return true
  }

  /** 获取当前 token（供 API 请求使用） */
  function getToken(): string | null {
    return token.value
  }

  // 初始化时自动检查 localStorage
  checkAuth()

  return {
    token,
    accountType,
    username,
    isAuthenticated,
    isAdmin,
    isPlayerLoggedIn,
    isAdminLoggedIn,
    checkAuth,
    login,
    logout,
    validateWithBackend,
    getToken,
  }
}

/** 获取 useAuth 单例 */
export function useAuth() {
  if (!_instance) {
    _instance = createAuth()
  }
  return _instance
}
