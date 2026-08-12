/**
 * # main.ts — 出题器入口
 *
 * 装配 Pinia（账号/题库）与 vue-router（登录 → 列表 → 编辑器）。
 * 不引入 vue-i18n：出题器面向中文出题者，UI 文案直接内联。
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { router } from './router'
import { applyInitialTheme } from './composables/useTheme'
import './styles/main.css'

// 挂载前应用持久化主题（CSS 变量随 <html data-theme> 即时生效，避免闪烁）
applyInitialTheme()

createApp(App).use(createPinia()).use(router).mount('#app')
