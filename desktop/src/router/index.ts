/**
 * # 路由配置
 *
 * 路由守卫链：
 * 1. 路径规范化 — 将无斜杠 URL 补上 `/`
 * 2. 鉴权守卫 — 检测 token，未认证则导向 AuthGate
 *
 * ## 路由表
 *
 * | 路径       | 名称       | 组件         | 鉴权 |
 * |-----------|-----------|-------------|------|
 * | /         | desktop   | DesktopView | 需要 |
 * | /login    | login     | LoginView   | 公开 |
 * | /auth-gate| auth-gate | AuthGateView| 公开 |
 */

import { createRouter, createWebHistory } from 'vue-router'

import DesktopView from '@/views/DesktopView.vue'
import LoginView from '@/views/LoginView.vue'
import AuthGateView from '@/views/AuthGate.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'desktop',
      component: DesktopView,
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
    },
    {
      path: '/auth-gate',
      name: 'auth-gate',
      component: AuthGateView,
    },
  ],
})

/**
 * 守卫 1：路径规范化 — 无斜杠 URL 自动补 `/`
 *
 * 例如访问 `/console` → 重定向到 `/console/`
 */
router.beforeEach((to, _from) => {
  const base = import.meta.env.BASE_URL // '/console/'
  const baseWithoutSlash = base.replace(/\/$/, '') // '/console'

  if (to.fullPath === baseWithoutSlash) {
    return base
  }
  return true
})

/**
 * 守卫 2：鉴权检查
 *
 * - 目标为 desktop → 需要 token，否则导向 AuthGate
 * - AuthGate 自身会再次检查 token，有则直接进入 desktop
 */
import { useAuth } from '@/composables/useAuth'

router.beforeEach((to, from) => {
  if (to.name === 'desktop') {
    const auth = useAuth()

    if (auth.isAuthenticated.value) {
      return true
    }

    // 避免死循环：从 auth-gate 或 login 过来的放行
    if (from.name === 'auth-gate' || from.name === 'login') {
      return true
    }

    // 未认证 → 导向鉴权网关
    return { name: 'auth-gate' }
  }

  return true
})

export default router
