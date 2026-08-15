import { createServer } from 'node:http'

import { createApp } from './app.js'
import { loadConfig } from './config.js'
import { attachWebSocketHub, WS_PATH_PREFIX } from './ws/hub.js'

const config = loadConfig()
const server = createServer(createApp())
attachWebSocketHub(server)

server.listen(config.port, () => {
  console.log(`[ellia-server] REST http://localhost:${config.port}/api`)
  console.log(`[ellia-server] WS   ws://localhost:${config.port}${WS_PATH_PREFIX}`)
  console.log(`[ellia-server] 初始 admin 播种（M1 落地 users 表）：${config.adminUsername}`)
})
