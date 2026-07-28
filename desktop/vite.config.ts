import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/**
 * Vite 插件：路径规范化 + SPA 回退 + Live2D 缓存头。
 *
 * 1. 将 `/console`（无尾部斜杠）301 重定向到 `/console/`（dev + preview 均生效）
 * 2. preview 模式下，`/console/` 直接返回 dist/index.html（避免 EISDIR）
 * 3. 为 Live2D 静态资源添加 24h 缓存头
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
      // 在静态文件中间件之前插入，直接返回 index.html
      // 避免 sirv 将 dist/ 当作目录处理导致 EISDIR
      const distIndex = resolve(__dirname, 'dist/index.html')
      const indexHtml = readFileSync(distIndex, 'utf-8')

      server.middlewares.use((req, res, next) => {
        // 仅拦截 SPA 入口路径，静态资源（assets/、images/ 等）放行
        if (req.url === '/console/' || req.url === '/console') {
          res.writeHead(200, { 'Content-Type': 'text/html' })
          res.end(indexHtml)
          return
        }
        next()
      })

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
