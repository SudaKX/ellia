import type { Server as HttpServer } from 'node:http'
import type { ClientMessage, ServerMessage } from '@ellia/puzzle-schema'
import { WebSocketServer, WebSocket } from 'ws'

/** WS 端点前缀：/ws/projects/:id（token 认证在 M1 加入） */
export const WS_PATH_PREFIX = '/ws'

/** M0 专用回显消息；M2 起由 plan-v1.md §4 的 join/sync/patch 协议替换 */
interface EchoMessage {
  type: 'echo'
  data: ClientMessage
}

type WireMessage = ServerMessage | EchoMessage

export function attachWebSocketHub(server: HttpServer): WebSocketServer {
  const wss = new WebSocketServer({ noServer: true })

  server.on('upgrade', (request, socket, head) => {
    const url = new URL(request.url ?? '/', 'http://localhost')
    if (!url.pathname.startsWith(WS_PATH_PREFIX)) return
    wss.handleUpgrade(request, socket, head, (ws) => wss.emit('connection', ws, request))
  })

  wss.on('connection', (ws) => {
    send(ws, { type: 'hello', service: 'ellia-server' })

    ws.on('message', (data) => {
      let message: ClientMessage
      try {
        message = JSON.parse(data.toString()) as ClientMessage
      } catch {
        send(ws, { type: 'error', reason: 'invalid-json' })
        return
      }
      if (message.type === 'ping') {
        send(ws, { type: 'pong' })
        return
      }
      send(ws, { type: 'echo', data: message })
    })
  })

  return wss
}

function send(ws: WebSocket, message: WireMessage): void {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message))
  }
}
