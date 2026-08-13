/**
 * # router — 出题器路由
 *
 * - `/login`：登录 / 注册
 * - `/questions`：题目列表（需登录）
 * - `/questions/new`：新建题目（需登录）
 * - `/questions/:id`：编辑题目（需登录，且本人/admin）
 *
 * 未登录访问受保护路由 → 重定向到 /login。
 */

import { createRouter, createWebHistory } from 'vue-router'

import LoginView from '@/views/LoginView.vue'
import QuestionListView from '@/views/QuestionListView.vue'
import QuestionEditorView from '@/views/QuestionEditorView.vue'
import { useAuthStore } from '@/stores/auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/questions' },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/questions', name: 'questions', component: QuestionListView, meta: { requiresAuth: true } },
    { path: '/questions/new', name: 'question-new', component: QuestionEditorView, meta: { requiresAuth: true } },
    { path: '/questions/:id', name: 'question-edit', component: QuestionEditorView, meta: { requiresAuth: true } },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: 'questions' }
  }
  return true
})
