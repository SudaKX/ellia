/**
 * # useAuthStore — 出题者账号（localStorage 模拟）
 *
 * 纯前端账号体系：
 * - 账号表存 localStorage（key `ellia.question.accounts`）
 * - **首个注册账号自动为管理员**（保证必有 admin），其余为 author
 * - 登录态存 localStorage（key `ellia.question.session`）
 *
 * ## 安全说明
 *
 * 密码仅做简易散列（djb2），纯前端演示场景，不具备真实安全性；
 * 后续切后端（见计划 B 节）时由服务端认证接管。
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

/** 账号记录 */
export interface AccountRecord {
  username: string
  passwordHash: string
  /** author 普通出题者 / admin 管理员 */
  role: 'author' | 'admin'
  createdAt: string
}

const ACCOUNTS_KEY = 'ellia.question.accounts'
const SESSION_KEY = 'ellia.question.session'

/** 简易散列（djb2）——非安全场景，仅避免明文存储 */
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

export const useAuthStore = defineStore('auth', () => {
  /** 当前登录用户名（持久化） */
  const sessionUsername = ref<string | null>(localStorage.getItem(SESSION_KEY))

  /** 当前登录账号（从账号表实时查找，账号被删则视为未登录） */
  const currentUser = computed<AccountRecord | null>(() => {
    if (!sessionUsername.value) return null
    return readAccounts().find((account) => account.username === sessionUsername.value) ?? null
  })

  const isLoggedIn = computed(() => currentUser.value !== null)
  const isAdmin = computed(() => currentUser.value?.role === 'admin')

  /**
   * 注册账号。首个注册账号自动为管理员。
   *
   * @param username - 用户名
   * @param password - 密码
   * @returns 结果（ok 表示成功并已登录）
   */
  function register(username: string, password: string): { ok: boolean; error?: string } {
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
    sessionUsername.value = name
    localStorage.setItem(SESSION_KEY, name)
    return { ok: true }
  }

  /**
   * 登录。
   *
   * @param username - 用户名
   * @param password - 密码
   * @returns 结果（ok 表示成功）
   */
  function login(username: string, password: string): { ok: boolean; error?: string } {
    const name = username.trim()
    const account = readAccounts().find((candidate) => candidate.username === name)
    if (!account || account.passwordHash !== hashPassword(password)) {
      return { ok: false, error: '用户名或密码错误' }
    }
    sessionUsername.value = name
    localStorage.setItem(SESSION_KEY, name)
    return { ok: true }
  }

  /** 退出登录 */
  function logout(): void {
    sessionUsername.value = null
    localStorage.removeItem(SESSION_KEY)
  }

  return { currentUser, isLoggedIn, isAdmin, register, login, logout }
})
