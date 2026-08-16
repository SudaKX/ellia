import { once } from 'node:events'
import { mkdtempSync } from 'node:fs'
import { createServer, type Server } from 'node:http'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import WebSocket from 'ws'

import { seedInitialAdmin } from '../src/auth/users.js'
import { createApp } from '../src/app.js'
import type { ServerConfig } from '../src/config.js'
import { closeDatabase, getDatabase, initDatabase } from '../src/db/database.js'
import { ensureMetaSeeded } from '../src/db/meta.js'
import { attachWebSocketHub } from '../src/ws/hub.js'

export const TEST_ADMIN_USERNAME = 'admin'
export const TEST_ADMIN_PASSWORD = 'secret123'

export function testConfig(): ServerConfig {
  return {
    port: 0,
    adminUsername: TEST_ADMIN_USERNAME,
    adminPassword: TEST_ADMIN_PASSWORD,
    databasePath: ':memory:',
    sessionTtlDays: 30,
    secureCookies: false,
    fileDataDir: mkdtempSync(join(tmpdir(), 'ellia-files-')),
    maxFileBytes: 50 * 1024 * 1024,
    entityHistoryLimit: 20,
  }
}

export interface TestContext {
  server: Server
  baseUrl: string
  wsUrl: string
  config: ServerConfig
  close: () => Promise<void>
}

export async function startTestServer(overrides: Partial<ServerConfig> = {}): Promise<TestContext> {
  initDatabase(':memory:')
  const config = { ...testConfig(), ...overrides }
  await seedInitialAdmin(getDatabase(), config)
  ensureMetaSeeded(config)
  const server = createApp(config).listen(0)
  await once(server, 'listening')
  const baseUrl = baseUrlOf(server)
  return {
    server,
    baseUrl,
    wsUrl: baseUrl.replace('http://', 'ws://'),
    config,
    close: async () => {
      server.close()
      await once(server, 'close')
      closeDatabase()
    },
  }
}

/** REST + WS 一体测试服务器：createApp + attachWebSocketHub */
export async function startTestServerWithWs(
  overrides: Partial<ServerConfig> = {},
): Promise<TestContext> {
  initDatabase(':memory:')
  const config = { ...testConfig(), ...overrides }
  await seedInitialAdmin(getDatabase(), config)
  ensureMetaSeeded(config)
  const server = createServer(createApp(config))
  attachWebSocketHub(server)
  server.listen(0)
  await once(server, 'listening')
  const baseUrl = baseUrlOf(server)
  return {
    server,
    baseUrl,
    wsUrl: baseUrl.replace('http://', 'ws://'),
    config,
    close: async () => {
      server.close()
      await once(server, 'close')
      closeDatabase()
    },
  }
}

function baseUrlOf(server: Server): string {
  const address = server.address()
  if (address === null || typeof address === 'string') {
    throw new Error('test server did not bind to a TCP port')
  }
  return `http://127.0.0.1:${address.port}`
}

export interface ApiResponse {
  status: number
  body: unknown
  cookie: string | undefined
}

export async function api(
  baseUrl: string,
  path: string,
  options: { method?: string; body?: unknown; cookie?: string } = {},
): Promise<ApiResponse> {
  const headers = new Headers()
  if (options.body !== undefined) headers.set('content-type', 'application/json')
  if (options.cookie) headers.set('cookie', options.cookie)

  const response = await fetch(baseUrl + path, {
    method: options.method ?? 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  const setCookie = response.headers.get('set-cookie')
  const cookie = setCookie === null ? undefined : setCookie.split(';')[0]
  let body: unknown = null
  const text = await response.text()
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }
  return { status: response.status, body, cookie }
}

export async function loginCookie(
  baseUrl: string,
  username = TEST_ADMIN_USERNAME,
  password = TEST_ADMIN_PASSWORD,
): Promise<string> {
  const response = await api(baseUrl, '/api/auth/login', {
    method: 'POST',
    body: { username, password },
  })
  if (response.status !== 200 || !response.cookie) {
    throw new Error(`login helper failed for ${username}: ${JSON.stringify(response.body)}`)
  }
  return response.cookie
}

export async function createProject(
  baseUrl: string,
  cookie: string,
  moduleId: string,
): Promise<{ id: string }> {
  const response = await api(baseUrl, '/api/projects', {
    method: 'POST',
    cookie,
    body: { module_id: moduleId, display_name: moduleId },
  })
  if (response.status !== 201) {
    throw new Error(`create project failed: ${JSON.stringify(response.body)}`)
  }
  return (response.body as { project: { id: string } }).project
}

export interface WsTestClient {
  ws: WebSocket
  closed: Promise<void>
  send: (message: unknown) => void
  waitFor: (
    type?: string,
    timeoutMs?: number,
    match?: (message: Record<string, unknown>) => boolean,
  ) => Promise<Record<string, unknown>>
  flush: (type?: string) => void
  close: () => Promise<void>
}

/** 以 cookie 会话连接项目 WS（ws 包客户端，支持自定义 header） */
export async function wsConnect(
  wsUrl: string,
  cookie: string,
  projectId: string,
): Promise<WsTestClient> {
  const ws = new WebSocket(`${wsUrl}/ws/projects/${encodeURIComponent(projectId)}`, {
    headers: { Cookie: cookie },
  })
  const queue = messageQueue(ws)
  await once(ws, 'open')
  const closed = new Promise<void>((resolve) => {
    ws.on('close', () => resolve())
  })
  return {
    ws,
    closed,
    send: (message: unknown) => {
      ws.send(JSON.stringify(message))
    },
    waitFor: (type?: string, timeoutMs = 2000, match?: (message: Record<string, unknown>) => boolean) =>
      queue.waitFor(type, timeoutMs, match),
    flush: (type?: string) => queue.flush(type),
    close: async () => {
      ws.close()
      await closed
    },
  }
}

export function wsRequest(client: WsTestClient, message: unknown): void {
  client.send(message)
}

interface MessageQueue {
  waitFor: (
    type?: string,
    timeoutMs?: number,
    match?: (message: Record<string, unknown>) => boolean,
  ) => Promise<Record<string, unknown>>
  flush: (type?: string) => void
}

interface PendingWait {
  type: string | undefined
  match: ((message: Record<string, unknown>) => boolean) | undefined
  resolve: (message: Record<string, unknown>) => void
  timer: NodeJS.Timeout
}

function matches(
  message: Record<string, unknown>,
  type: string | undefined,
  match: ((message: Record<string, unknown>) => boolean) | undefined,
): boolean {
  if (type !== undefined && message.type !== type) return false
  if (match && !match(message)) return false
  return true
}

const queues = new WeakMap<WebSocket, MessageQueue>()

function messageQueue(ws: WebSocket): MessageQueue {
  const existing = queues.get(ws)
  if (existing) return existing

  const waiting: PendingWait[] = []
  const buffer: Record<string, unknown>[] = []
  ws.on('message', (data) => {
    let message: Record<string, unknown>
    try {
      message = JSON.parse(data.toString()) as Record<string, unknown>
    } catch {
      return
    }
    const index = waiting.findIndex((pending) =>
      matches(message, pending.type, pending.match),
    )
    if (index >= 0) {
      const [pending] = waiting.splice(index, 1)
      clearTimeout(pending.timer)
      pending.resolve(message)
      return
    }
    buffer.push(message)
  })

  const queue: MessageQueue = {
    waitFor: (type?: string, timeoutMs = 2000, match?: (message: Record<string, unknown>) => boolean) => {
      const bufferedIndex = buffer.findIndex((message) => matches(message, type, match))
      if (bufferedIndex >= 0) {
        const [message] = buffer.splice(bufferedIndex, 1)
        return Promise.resolve(message)
      }
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          const index = waiting.indexOf(pending)
          if (index >= 0) waiting.splice(index, 1)
          reject(
            new Error(
              `timed out waiting for WS message${type ? ` of type ${type}` : ''}`,
            ),
          )
        }, timeoutMs)
        const pending: PendingWait = { type, match, resolve, timer }
        waiting.push(pending)
      })
    },
    flush: (type?: string) => {
      for (let index = buffer.length - 1; index >= 0; index -= 1) {
        if (type === undefined || buffer[index]?.type === type) buffer.splice(index, 1)
      }
    },
  }
  queues.set(ws, queue)
  return queue
}

export async function waitForMessage(
  ws: WebSocket,
  type?: string,
  timeoutMs = 2000,
): Promise<Record<string, unknown>> {
  return messageQueue(ws).waitFor(type, timeoutMs)
}
