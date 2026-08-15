import express from 'express'
import type { Express } from 'express'
import { SYNC_PROTOCOL_VERSION } from '@ellia/puzzle-schema'

/**
 * Express 应用工厂。
 * REST 路由全部挂在 /api 下（M1 起加入 auth / admin / projects）。
 */
export function createApp(): Express {
  const app = express()
  app.use(express.json())

  app.get('/api/health', (_req, res) => {
    res.json({
      ok: true,
      service: 'ellia-server',
      sync_protocol_version: SYNC_PROTOCOL_VERSION,
      time: new Date().toISOString(),
    })
  })

  return app
}
