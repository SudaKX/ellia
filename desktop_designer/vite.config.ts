import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/**
 * # desktop_designer — 出题器 Vite 配置
 *
 * 独立 Vue3 项目（与 desktop 同构）。dev server 固定端口 5174：
 * 导出功能生成的 published-questions.json 可放入 public/ 后，
 * 由 desktop（USE_PUBLISHED_QUESTIONS=true）通过 http://localhost:5174/published-questions.json 拉取。
 */
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5174,
  },
})
