import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// 开发期代理目标：apps/server（可用 VITE_API_PROXY_TARGET 覆盖，如 http://localhost:4000）
const API_TARGET = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:3000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    watch: {
      // Windows 下 Vite 的默认文件监听会短暂占用文件句柄，导致外部工具写入时出现
      // ReplaceFileW EIO；使用轮询模式可避免该问题。
      usePolling: true,
      interval: 100,
    },
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
      '/ws': { target: API_TARGET.replace(/^http/, 'ws'), ws: true },
    },
  },
})
