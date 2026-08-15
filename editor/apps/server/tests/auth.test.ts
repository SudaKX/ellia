import assert from 'node:assert/strict'
import { afterEach, beforeEach, describe, it } from 'node:test'

import { createInvite } from '../src/auth/invites.js'
import { seedInitialAdmin, findUserByUsername, countAdmins } from '../src/auth/users.js'
import { getDatabase } from '../src/db/database.js'
import { api, loginCookie, startTestServer, type TestContext } from './helpers.js'

describe('auth API', () => {
  let context: TestContext

  beforeEach(async () => {
    context = await startTestServer()
  })

  afterEach(async () => {
    await context.close()
  })

  async function createAdminInvite(ttlSeconds = 3600): Promise<string> {
    const cookie = await loginCookie(context.baseUrl)
    const response = await api(context.baseUrl, '/api/admin/invites', {
      method: 'POST',
      cookie,
      body: { expires_in_seconds: ttlSeconds },
    })
    assert.equal(response.status, 201)
    const code = (response.body as { code?: string }).code
    assert.ok(code)
    return code
  }

  it('播种初始 admin，且重复播种不产生第二个 admin', async () => {
    await seedInitialAdmin(getDatabase(), context.config)
    assert.equal(countAdmins(getDatabase()), 1)

    const cookie = await loginCookie(context.baseUrl)
    const me = await api(context.baseUrl, '/api/auth/me', { cookie })
    assert.equal(me.status, 200)
    const user = (me.body as { user: { username: string; role: string } }).user
    assert.equal(user.username, 'admin')
    assert.equal(user.role, 'admin')
  })

  it('使用一次性邀请码注册成功，并建立 cookie 会话', async () => {
    const code = await createAdminInvite()
    const response = await api(context.baseUrl, '/api/auth/register', {
      method: 'POST',
      body: { username: 'alice', password: 'password123', invite_code: code },
    })
    assert.equal(response.status, 201)
    const user = (response.body as { user: { username: string; role: string } }).user
    assert.equal(user.username, 'alice')
    assert.equal(user.role, 'user')
    assert.ok(response.cookie)

    const me = await api(context.baseUrl, '/api/auth/me', { cookie: response.cookie })
    assert.equal(me.status, 200)
    assert.equal((me.body as { user: { username: string } }).user.username, 'alice')
  })

  it('邀请码只能使用一次，重复注册返回 400', async () => {
    const code = await createAdminInvite()
    const first = await api(context.baseUrl, '/api/auth/register', {
      method: 'POST',
      body: { username: 'alice', password: 'password123', invite_code: code },
    })
    assert.equal(first.status, 201)

    const second = await api(context.baseUrl, '/api/auth/register', {
      method: 'POST',
      body: { username: 'bob', password: 'password123', invite_code: code },
    })
    assert.equal(second.status, 400)
    assert.equal((second.body as { error: { code: string } }).error.code, 'INVITE_USED')
  })

  it('过期或无效邀请码注册返回 400', async () => {
    const db = getDatabase()
    const admin = findUserByUsername(db, 'admin')
    assert.ok(admin)
    const expiredInvite = createInvite(db, admin.id, new Date(Date.now() - 1000).toISOString())

    const expired = await api(context.baseUrl, '/api/auth/register', {
      method: 'POST',
      body: { username: 'alice', password: 'password123', invite_code: expiredInvite.code },
    })
    assert.equal(expired.status, 400)
    assert.equal((expired.body as { error: { code: string } }).error.code, 'INVITE_EXPIRED')

    const invalid = await api(context.baseUrl, '/api/auth/register', {
      method: 'POST',
      body: { username: 'alice', password: 'password123', invite_code: 'not-a-real-code' },
    })
    assert.equal(invalid.status, 400)
    assert.equal((invalid.body as { error: { code: string } }).error.code, 'INVALID_INVITE')
  })

  it('重复用户名注册返回 409', async () => {
    const firstCode = await createAdminInvite()
    await api(context.baseUrl, '/api/auth/register', {
      method: 'POST',
      body: { username: 'alice', password: 'password123', invite_code: firstCode },
    })
    const secondCode = await createAdminInvite()
    const response = await api(context.baseUrl, '/api/auth/register', {
      method: 'POST',
      body: { username: 'alice', password: 'password456', invite_code: secondCode },
    })
    assert.equal(response.status, 409)
    assert.equal((response.body as { error: { code: string } }).error.code, 'USERNAME_TAKEN')
  })

  it('注册参数校验失败返回统一错误结构', async () => {
    const response = await api(context.baseUrl, '/api/auth/register', {
      method: 'POST',
      body: { username: 'x', password: 'short', invite_code: '' },
    })
    assert.equal(response.status, 400)
    const error = (response.body as { error: { code: string; message: string } }).error
    assert.equal(error.code, 'VALIDATION')
    assert.ok(error.message.length > 0)
  })

  it('登录成功建立会话，密码错误返回 401 且不泄露用户名是否存在', async () => {
    const wrong = await api(context.baseUrl, '/api/auth/login', {
      method: 'POST',
      body: { username: 'admin', password: 'wrong-password' },
    })
    assert.equal(wrong.status, 401)
    assert.equal((wrong.body as { error: { code: string } }).error.code, 'INVALID_CREDENTIALS')

    const cookie = await loginCookie(context.baseUrl)
    const me = await api(context.baseUrl, '/api/auth/me', { cookie })
    assert.equal(me.status, 200)
  })

  it('登出使当前会话失效', async () => {
    const cookie = await loginCookie(context.baseUrl)
    const logout = await api(context.baseUrl, '/api/auth/logout', { method: 'POST', cookie })
    assert.equal(logout.status, 204)

    const me = await api(context.baseUrl, '/api/auth/me', { cookie })
    assert.equal(me.status, 401)
  })

  it('未登录访问 me 返回 401，未登录访问 admin API 也返回 401', async () => {
    const me = await api(context.baseUrl, '/api/auth/me')
    assert.equal(me.status, 401)
    assert.equal((me.body as { error: { code: string } }).error.code, 'UNAUTHORIZED')

    const users = await api(context.baseUrl, '/api/admin/users')
    assert.equal(users.status, 401)
  })
})
