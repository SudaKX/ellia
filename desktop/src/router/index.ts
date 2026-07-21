import { createRouter, createWebHistory } from 'vue-router'

import DesktopView from '@/views/DesktopView.vue'
import LoginView from '@/views/LoginView.vue'

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
  ],
})

// 访问根路径时自动跳转到登录页，但从登录页跳转过来的放行
router.beforeEach((to, from, next) => {
  if (to.name === 'desktop' && from.name !== 'login') {
    next({ name: 'login' })
  } else {
    next()
  }
})

export default router
