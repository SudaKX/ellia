import { randomUUID } from 'node:crypto'
import type { Server as HttpServer, IncomingMessage } from 'node:http'
import type { Duplex } from 'node:stream'

import type * as mediasoup from 'mediasoup'
import { WebSocketServer, WebSocket } from 'ws'

import { findSessionWithUser, parseSessionCookie } from '../auth/sessions.js'
import { loadConfig } from '../config.js'
import { getDatabase } from '../db/database.js'
import { ApiError } from '../errors.js'
import { findProjectById } from '../services/projects.js'
import { getVoiceManager } from './manager.js'

export const VOICE_WS_PATH_PREFIX = '/ws'

type DtlsParameters = mediasoup.types.DtlsParameters
type RtpCapabilities = mediasoup.types.RtpCapabilities
type MediaKind = mediasoup.types.MediaKind
type RtpParameters = mediasoup.types.RtpParameters

type VoiceClientMessage = (
  | { type: 'channels.join'; channel_id: string }
  | { type: 'channels.leave' }
  | { type: 'rtp.capabilities'; rtp_capabilities: RtpCapabilities }
  | {
      type: 'transport.connect'
      transport_id: string
      dtls_parameters: DtlsParameters
    }
  | {
      type: 'produce'
      transport_id: string
      kind: MediaKind
      rtp_parameters: RtpParameters
    }
  | { type: 'consumer.resume'; consumer_id: string }
  | { type: 'mic.state'; muted: boolean }
  | { type: 'speaking'; speaking: boolean }
) & { ref?: string }

interface VoiceConnectionContext {
  connectionId: string
  projectId: string
}

const contexts = new Map<WebSocket, VoiceConnectionContext>()

export function attachVoiceSocket(server: HttpServer): WebSocketServer {
  const wss = new WebSocketServer({ noServer: true })
  const manager = getVoiceManager(loadConfig())
  void manager.initialize().catch((error) => {
    console.error('[ellia-server] voice mediasoup init failed:', error)
  })

  server.on('upgrade', (request, socket, head) => {
    const url = new URL(request.url ?? '/', 'http://localhost')
    const match = url.pathname.match(/^\/ws\/projects\/([^/]+)\/voice$/)
    if (!match) return

    let projectId: string
    try {
      projectId = decodeURIComponent(match[1] ?? '')
    } catch {
      rejectUpgrade(socket, 400, 'Bad Request')
      return
    }
    if (!projectId) {
      rejectUpgrade(socket, 400, 'Bad Request')
      return
    }

    const token = parseSessionCookie(request.headers.cookie ?? '')
    const session = token ? findSessionWithUser(getDatabase(), token) : undefined
    if (!session) {
      rejectUpgrade(socket, 401, 'Unauthorized')
      return
    }
    if (!findProjectById(projectId)) {
      rejectUpgrade(socket, 404, 'Project not found')
      return
    }

    const context: VoiceConnectionContext = {
      connectionId: randomUUID(),
      projectId,
    }
    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit('connection', ws, request, context, session.user)
    })
  })

  wss.on(
    'connection',
    (
      ws: WebSocket,
      _request: IncomingMessage,
      context: VoiceConnectionContext,
      user: { id: string; username: string },
    ) => {
      contexts.set(ws, context)
      manager.registerConnection(
        context.connectionId,
        context.projectId,
        user.id,
        user.username,
        ws,
      )
      send(ws, { type: 'voice.ready', project_id: context.projectId })

      ws.on('message', (data) => {
        let message: VoiceClientMessage
        try {
          message = JSON.parse(data.toString()) as VoiceClientMessage
        } catch {
          sendError(ws, 'BAD_JSON', '消息不是合法 JSON')
          return
        }
        void handleMessage(ws, context, manager, message)
      })

      ws.on('close', () => {
        contexts.delete(ws)
        void manager.unregisterConnection(context.connectionId).catch((error) => {
          console.error('[ellia-server] voice cleanup error:', error)
        })
      })

      ws.on('error', () => {
        // close 事件负责清理
      })
    },
  )

  return wss
}

async function handleMessage(
  ws: WebSocket,
  context: VoiceConnectionContext,
  manager: ReturnType<typeof getVoiceManager>,
  message: VoiceClientMessage,
): Promise<void> {
  try {
    switch (message.type) {
      case 'channels.join':
        if (typeof message.channel_id !== 'string' || !message.channel_id) {
          throw new ApiError(400, 'VALIDATION', 'channel_id 不能为空')
        }
        await manager.joinChannel(context.connectionId, message.channel_id)
        sendAck(ws, message.ref)
        return
      case 'channels.leave':
        await manager.leaveChannel(context.connectionId)
        sendAck(ws, message.ref)
        return
      case 'rtp.capabilities':
        if (typeof message.rtp_capabilities !== 'object' || message.rtp_capabilities === null) {
          throw new ApiError(400, 'VALIDATION', 'rtp_capabilities 必须是对象')
        }
        await manager.setRtpCapabilities(context.connectionId, message.rtp_capabilities)
        sendAck(ws, message.ref)
        return
      case 'transport.connect': {
        if (typeof message.transport_id !== 'string' || !message.transport_id) {
          throw new ApiError(400, 'VALIDATION', 'transport_id 不能为空')
        }
        if (typeof message.dtls_parameters !== 'object' || message.dtls_parameters === null) {
          throw new ApiError(400, 'VALIDATION', 'dtls_parameters 必须是对象')
        }
        await manager.handleTransportConnect(
          context.connectionId,
          message.transport_id,
          message.dtls_parameters,
        )
        if (message.ref) {
          send(ws, { type: 'transport.connected', ref: message.ref })
        }
        return
      }
      case 'produce': {
        if (typeof message.transport_id !== 'string' || !message.transport_id) {
          throw new ApiError(400, 'VALIDATION', 'transport_id 不能为空')
        }
        if (message.kind !== 'audio') {
          throw new ApiError(400, 'VALIDATION', '当前只支持音频')
        }
        if (typeof message.rtp_parameters !== 'object' || message.rtp_parameters === null) {
          throw new ApiError(400, 'VALIDATION', 'rtp_parameters 必须是对象')
        }
        const producerId = await manager.handleProduce(
          context.connectionId,
          message.transport_id,
          message.kind,
          message.rtp_parameters,
        )
        if (message.ref) {
          send(ws, { type: 'produce.created', ref: message.ref, producer_id: producerId })
        } else {
          send(ws, { type: 'producer.created', producer_id: producerId })
        }
        return
      }
      case 'consumer.resume': {
        if (typeof message.consumer_id !== 'string' || !message.consumer_id) {
          throw new ApiError(400, 'VALIDATION', 'consumer_id 不能为空')
        }
        await manager.handleConsumerResume(context.connectionId, message.consumer_id)
        if (message.ref) {
          send(ws, { type: 'consumer.resumed', ref: message.ref })
        }
        return
      }
      case 'mic.state':
        await manager.setMuted(context.connectionId, message.muted === true)
        sendAck(ws, message.ref)
        return
      case 'speaking':
        await manager.setSpeaking(context.connectionId, message.speaking === true)
        sendAck(ws, message.ref)
        return
      default:
        sendError(ws, 'VALIDATION', `未知消息类型: ${String((message as { type?: string }).type)}`)
    }
  } catch (error) {
    const code = error instanceof ApiError ? error.code : 'INTERNAL'
    const errorMessage = error instanceof ApiError ? error.message : '内部错误'
    if (!(error instanceof ApiError)) {
      console.error('[ellia-server] voice ws handler error:', error)
    }
    sendError(ws, code, errorMessage)
  }
}

function sendAck(ws: WebSocket, ref?: string): void {
  if (ref) send(ws, { type: 'ack', ref })
}

function sendError(ws: WebSocket, code: string, message: string): void {
  send(ws, { type: 'error', code, message })
}

function send(ws: WebSocket, message: Record<string, unknown>): void {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message))
  }
}

function rejectUpgrade(socket: Duplex, status: number, message: string): void {
  const body = `${message}\n`
  socket.write(
    `HTTP/1.1 ${status} ${status === 401 ? 'Unauthorized' : status === 404 ? 'Not Found' : 'Bad Request'}\r\n` +
      'Connection: close\r\n' +
      'Content-Type: text/plain; charset=utf-8\r\n' +
      `Content-Length: ${Buffer.byteLength(body)}\r\n\r\n${body}`,
  )
  socket.destroy()
}
