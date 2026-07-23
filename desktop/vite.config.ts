import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/**
 * Vite 插件：为 Live2D 静态资源添加缓存头。
 * 模型文件（model3.json / moc3 / textures / motions）体积大且不常变，
 * 设置 24h 缓存避免每次刷新重新下载。
 */
function live2dCacheHeaders(): import('vite').Plugin {
  return {
    name: 'live2d-cache-headers',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url?.startsWith('/live2d/')) {
          res.setHeader('Cache-Control', 'public, max-age=86400')
        }
        next()
      })
    },
  }
}

export default defineConfig({
  base: '/console/',
  plugins: [vue(), live2dCacheHeaders()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
