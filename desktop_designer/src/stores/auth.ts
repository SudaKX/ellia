/**
 * # useAuthStore — 出题者账号（远程后端优先，localStorage 回退）
 *
 * 两种模式（config/api.ts 的 USE_REMOTE_API 控制）：
 * - 远程：登录/注册调用 server/ 的 /api/v1/auth/*（JWT），会话存 localStorage
 * - 本地：纯前端账号表模拟（首个注册为管理员）
 *
 * 登录态统一为 session `{ token?, username, role }`，
 * 供 useQuestionApi / 组件读取当前用户。
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { QUESTION_API_BASE, USE_REMOTE_API } from '@/config/api'

/** 账号记录（仅本地模拟模式使用） */
interface AccountRecord {
  username: string
  passwordHash: string
  /** author 普通出题者 / admin 管理员 */
  role: 'author' | 'admin'
  createdAt: string
}

/** 登录会话（两种模式共用） */
export interface Session {
  token?: string
  username: string
  role: 'author' | 'admin'
}

const ACCOUNTS_KEY = 'ellia.question.accounts'
const SESSION_KEY = 'ellia.question.session'

// ─── 本地模拟模式工具 ───────────────────────────────

/** 简易散列（djb2）——仅本地模拟模式，非安全场景 */
function hashPassword(value: string): string {
  let hash = 5381
  for (let i = 0; i < value.length; i++) {
    hash = ((hash << 5) + hash + value.charCodeAt(i)) >>> 0
  }
  return hash.toString(16)
}

function readAccounts(): AccountRecord[] {
  try {
    return JSON.parse(localStorage.getItem(ACCOUNTS_KEY) ?? '[]') as AccountRecord[]
  } catch {
    return []
  }
}

function writeAccounts(accounts: AccountRecord[]): void {
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts))
}

function readSession(): Session | null {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY) ?? 'null') as Session | null
  } catch {
    return null
  }
}

function writeSession(session: Session): void {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

function clearSession(): void {
  localStorage.removeItem(SESSION_KEY)
}

// ─── 远程模式 API ───────────────────────────────────

async function remoteLogin(username: string, password: string): Promise<{ ok: boolean; error?: string; session?: Session }> {
  try {
    const response = await fetch(`${QUESTION_API_BASE}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    const data = await response.json()
    if (!response.ok) return { ok: false, error: data.error ?? '登录失败' }
    const session: Session = { token: data.access_token, username: data.user.username, role: data.user.role }
    writeSession(session)
    return { ok: true, session }
  } catch {
    return { ok: false, error: '无法连接后端，请确认 server/ 已启动' }
  }
}

async function remoteRegister(username: string, password: string): Promise<{ ok: boolean; error?: string; session?: Session }> {
  try {
    const response = await fetch(`${QUESTION_API_BASE}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    const data = await response.json()
    if (!response.ok) return { ok: false, error: data.error ?? '注册失败' }
    const session: Session = { token: data.access_token, username: data.user.username, role: data.user.role }
    writeSession(session)
    return { ok: true, session }
  } catch {
    return { ok: false, error: '无法连接后端，请确认 server/ 已启动' }
  }
}

// ─── 本地模拟模式逻辑 ───────────────────────────────

function localLogin(username: string, password: string): { ok: boolean; error?: string; session?: Session } {
  const name = username.trim()
  const account = readAccounts().find((candidate) => candidate.username === name)
  if (!account || account.passwordHash !== hashPassword(password)) {
    return { ok: false, error: '用户名或密码错误' }
  }
  const session: Session = { username: name, role: account.role }
  writeSession(session)
  return { ok: true, session }
}

function localRegister(username: string, password: string): { ok: boolean; error?: string; session?: Session } {
  const name = username.trim()
  if (!name || !password) return { ok: false, error: '用户名和密码不能为空' }
  const accounts = readAccounts()
  if (accounts.some((account) => account.username === name)) {
    return { ok: false, error: '用户名已存在' }
  }
  const role: AccountRecord['role'] = accounts.length === 0 ? 'admin' : 'author'
  accounts.push({
    username: name,
    passwordHash: hashPassword(password),
    role,
    createdAt: new Date().toISOString(),
  })
  writeAccounts(accounts)
  const session: Session = { username: name, role }
  writeSession(session)
  return { ok: true, session }
}

export const useAuthStore = defineStore('auth', () => {
  /** 当前登录会话（持久化） */
  const session = ref<Session | null>(readSession())

  /** 当前用户（统一给 useQuestionApi / 组件读取） */
  const currentUser = computed(() => {
    const value = session.value
    return value ? { username: value.username, role: value.role } : null
  })

  const isLoggedIn = computed(() => currentUser.value !== null)
  const isAdmin = computed(() => currentUser.value?.role === 'admin')

  /**
   * 注册并登录（远程 / 本地按配置）。
   * 远程模式所有账号注册后为 author；本地模式首个账号为 admin。
   */
  async function register(username: string, password: string): Promise<{ ok: boolean; error?: string }> {
    const result = USE_REMOTE_API ? await remoteRegister(username, password) : localRegister(username, password)
    if (result.ok && result.session) session.value = result.session
    return result
  }

  /** 登录（远程 / 本地按配置） */
  async function login(username: string, password: string): Promise<{ ok: boolean; error?: string }> {
    const result = USE_REMOTE_API ? await remoteLogin(username, password) : localLogin(username, password)
    if (result.ok && result.session) session.value = result.session
    return result
  }

  /** 退出登录 */
  function logout(): void {
    clearSession()
    session.value = null
  }

  return { currentUser, isLoggedIn, isAdmin, register, login, logout }
})
