import { mkdirSync } from 'node:fs'
import { createServer } from 'node:http'
import path from 'node:path'

import { seedInitialAdmin } from './auth/users.js'
import { createApp } from './app.js'
import { loadConfig } from './config.js'
import { getDatabase, initDatabase } from './db/database.js'
import { ensureMetaSeeded } from './db/meta.js'
import { attachWebSocketHub, WS_PATH_PREFIX } from './ws/hub.js'

const config = loadConfig()
initDatabase(config.databasePath)
await seedInitialAdmin(getDatabase(), config)
ensureMetaSeeded(config)
mkdirSync(path.resolve(config.fileDataDir), { recursive: true })

const server = createServer(createApp(config))
attachWebSocketHub(server)

server.listen(config.port, () => {
  console.log(`[ellia-server] REST http://localhost:${config.port}/api`)
  console.log(`[ellia-server] WS   ws://localhost:${config.port}${WS_PATH_PREFIX}`)
  console.log(`[ellia-server] 初始 admin：${config.adminUsername}`)
  console.log(`[ellia-server] SQLite：${config.databasePath}`)
  console.log(`[ellia-server] 文件目录：${path.resolve(config.fileDataDir)}`)
})
