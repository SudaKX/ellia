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
import './styles/main.css'

createApp(App).use(createPinia()).use(router).mount('#app')
