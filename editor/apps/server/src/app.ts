import express from 'express'
import type { Express } from 'express'
import { SYNC_PROTOCOL_VERSION } from '@ellia/puzzle-schema'

import { loadConfig, type ServerConfig } from './config.js'
import { errorHandler, notFoundHandler } from './errors.js'
import { adminRouter } from './routes/admin.js'
import { authRouter } from './routes/auth.js'

/**
 * Express 应用工厂。
 * REST 路由全部挂在 /api 下；配置注入到 app.locals.config 供中间件读取。
 */
export function createApp(config: ServerConfig = loadConfig()): Express {
  const app = express()
  app.locals.config = config
  app.use(express.json())

  app.get('/api/health', (_req, res) => {
    res.json({
      ok: true,
      service: 'ellia-server',
      sync_protocol_version: SYNC_PROTOCOL_VERSION,
      time: new Date().toISOString(),
    })
  })

  app.use('/api/auth', authRouter)
  app.use('/api/admin', adminRouter)
  app.use('/api', notFoundHandler)
  app.use(errorHandler)

  return app
}
