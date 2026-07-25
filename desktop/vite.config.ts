import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/**
 * Vite 插件：路径规范化 + Live2D 缓存头。
 *
 * 1. 将 `/console`（无尾部斜杠）301 重定向到 `/console/`（dev + preview 均生效）
 * 2. 为 Live2D 静态资源添加 24h 缓存头
 *
 * 注意：如果生产环境用 nginx / caddy 等反向代理，需在服务器层配置同样的重定向规则：
 *
 *   nginx:  rewrite ^/console$ /console/ permanent;
 *   caddy:  redir /console /console/ 301
 */
function consoleRedirectPlugin(): import('vite').Plugin {
  const redirectMiddleware: import('vite').Connect.NextHandleFunction = (req, res, next) => {
    if (req.url === '/console') {
      res.writeHead(301, { Location: '/console/' })
      res.end()
      return
    }
    next()
  }

  const cacheMiddleware: import('vite').Connect.NextHandleFunction = (req, res, next) => {
    if (req.url?.startsWith('/live2d/')) {
      res.setHeader('Cache-Control', 'public, max-age=86400')
    }
    next()
  }

  return {
    name: 'console-redirect',
    configureServer(server) {
      server.middlewares.use(redirectMiddleware)
      server.middlewares.use(cacheMiddleware)
    },
    configurePreviewServer(server) {
      server.middlewares.use(redirectMiddleware)
      server.middlewares.use(cacheMiddleware)
    },
  }
}

export default defineConfig({
  base: '/console/',
  plugins: [vue(), consoleRedirectPlugin()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
