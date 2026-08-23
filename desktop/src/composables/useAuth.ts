/**
 * # 鉴权状态管理
 *
 * 基于 Token 的鉴权系统，支持玩家账户和管理员账户两套登录态。
 * 双模式运行（开关见 `src/config/api.ts` 的 `USE_REAL_API`）：
 * - **Mock 模式**（默认）：token 存 localStorage，纯本地判定 —— 支持单独部署。
 * - **真实模式**：对接后端 Ellia Mythos API。
 *
 * ## 真实模式的鉴权通道（后端契约）
 *
 * - 登录/注册：`POST /api/v1/auth/login` 返回 `{access_token, token_type, expires_in}`，
 *   并 Set-Cookie 刷新令牌（HttpOnly，前端读不到）。
 * - 会话恢复：**后端没有 `/auth/validate` 端点**，改用 `POST /api/v1/auth/refresh`
 *   换新 access token（靠浏览器自动携带的 HttpOnly Cookie）。
 * - 登出：`POST /api/v1/auth/logout`（Bearer），通知后端删除 refresh Cookie。
 * - access token 默认 15 分钟过期；按后端安全文档建议生产应存内存而非 localStorage，
 *   当前为保持双模式行为一致仍落 localStorage，刷新页面后由 `validateWithBackend()`
 *   经 refresh 端点换新，过期 token 会被自动替换。
 *
 * ## localStorage 存储键（Mock 模式为主；真实模式兼容保留）
 *
 * | 键                     | 内容               | 说明                  |
 * |------------------------|-------------------|----------------------|
 * | `ell_auth_token`       | JWT / session token | 当前活跃的认证令牌       |
 * | `ell_player_logged_in` | `"true"` / 不存在   | 玩家账户是否已登录       |
 * | `ell_admin_logged_in`  | `"true"` / 不存在   | 管理员账户是否已登录     |
 *
 * ## 使用示例
 *
 * ```ts
 * import { useAuth } from '@/composables/useAuth'
 * const auth = useAuth()
 * auth.login('player', 'token', 'Alice')
 * await auth.validateWithBackend()  // 进入登录页时校验（真实模式 = refresh 续期）
 * await auth.refreshToken()         // 401 后主动换新 token
 * ```
 */

import { computed, ref } from 'vue'
import { useDesktopStore } from '@/stores/desktop'
import { startMediaPrecache } from '@/utils/mediaPrecache'
import { AUTH_ENDPOINTS, USE_REAL_API } from '@/config/api'

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
    desktop.privilegeClass = type === 'admin' ? 'ADMIN' : 'LIMITED'

    // 登录成功后后台预缓存多媒体资源到用户侧（fire-and-forget，见 utils/mediaPrecache）
    void startMediaPrecache()
  }

  /** 退出登录：清除所有认证状态；真实模式额外通知后端删除 refresh Cookie */
  function logout(): void {
    // 真实模式：异步通知后端登出（删除 HttpOnly refresh Cookie），失败忽略，本地照常清理
    if (USE_REAL_API && token.value) {
      fetch(AUTH_ENDPOINTS.logout, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token.value}` },
      }).catch(() => undefined)
    }

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
   * 后端校验：进入登录页时调用，验证当前会话是否仍然有效。
   *
   * - **真实模式**：后端没有 `/auth/validate`，改调 `POST /api/v1/auth/refresh`
   *   （靠 HttpOnly refresh Cookie 换新 access token），成功即视为会话有效。
   * - **Mock 模式**：本地 token 存在即视为有效。
   *
   * 切换真实 API：将 `src/config/api.ts` 中 `USE_REAL_API` 改为 `true` 并设置 `API_BASE`。
   */
  async function validateWithBackend(): Promise<boolean> {
    const savedToken = localStorage.getItem(TOKEN_KEY)

    if (!savedToken) {
      logout()
      return false
    }

    if (USE_REAL_API) {
      return refreshToken()
    }

    // Mock 模式：本地 token 存在即认为有效
    return true
  }

  /**
   * 刷新 access token（真实模式，后端 `POST /api/v1/auth/refresh`）。
   *
   * - 无 body，靠浏览器自动携带的 HttpOnly refresh Cookie 鉴权；
   * - 成功返回 `{access_token, token_type, expires_in}`，用新 token 更新内存与本地；
   * - 失败（cookie 过期/无效）→ 清除会话，返回 false。
   *
   * Mock 模式无后端，直接返回 true（本地 token 视为有效）。
   */
  async function refreshToken(): Promise<boolean> {
    if (!USE_REAL_API) return true
    try {
      const res = await fetch(AUTH_ENDPOINTS.refresh, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      if (!res.ok) {
        logout()
        return false
      }
      const data = (await res.json()) as { access_token?: string; token_type?: string; expires_in?: number }
      if (!data.access_token) {
        logout()
        return false
      }
      // 用新 token 覆盖（内存 + localStorage，后续请求继续带新 Bearer）
      token.value = data.access_token
      localStorage.setItem(TOKEN_KEY, data.access_token)
      return true
    } catch {
      logout()
      return false
    }
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
    refreshToken,
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
