import { once } from 'node:events'
import type { Server } from 'node:http'

import { seedInitialAdmin } from '../src/auth/users.js'
import { createApp } from '../src/app.js'
import type { ServerConfig } from '../src/config.js'
import { closeDatabase, getDatabase, initDatabase } from '../src/db/database.js'

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
  }
}

export interface TestContext {
  server: Server
  baseUrl: string
  config: ServerConfig
  close: () => Promise<void>
}

export async function startTestServer(): Promise<TestContext> {
  initDatabase(':memory:')
  const config = testConfig()
  await seedInitialAdmin(getDatabase(), config)
  const server = createApp(config).listen(0)
  await once(server, 'listening')
  const address = server.address()
  if (address === null || typeof address === 'string') {
    throw new Error('test server did not bind to a TCP port')
  }
  return {
    server,
    baseUrl: `http://127.0.0.1:${address.port}`,
    config,
    close: async () => {
      server.close()
      await once(server, 'close')
      closeDatabase()
    },
  }
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
