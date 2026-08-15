import assert from 'node:assert/strict'
import { afterEach, beforeEach, describe, it } from 'node:test'

import { api, loginCookie, startTestServer, type TestContext } from './helpers.js'

interface InviteItem {
  code: string
  expires_at: string
  status: 'unused' | 'used' | 'expired'
}

interface UserItem {
  id: string
  username: string
  role: 'user' | 'admin'
}

describe('admin API', () => {
  let context: TestContext

  beforeEach(async () => {
    context = await startTestServer()
  })

  afterEach(async () => {
    await context.close()
  })

  async function adminCookie(): Promise<string> {
    return loginCookie(context.baseUrl)
  }

  async function createUserViaRegister(username: string): Promise<string> {
    const admin = await adminCookie()
    const created = await api(context.baseUrl, '/api/admin/invites', {
      method: 'POST',
      cookie: admin,
      body: { expires_in_seconds: 3600 },
    })
    assert.equal(created.status, 201)
    const code = (created.body as { code: string }).code
    const registered = await api(context.baseUrl, '/api/auth/register', {
      method: 'POST',
      body: { username, password: 'password123', invite_code: code },
    })
    assert.equal(registered.status, 201)
    return registered.cookie as string
  }

  it('admin 可生成邀请码，缺省有效期 7 天；非法参数返回 400', async () => {
    const admin = await adminCookie()
    const created = await api(context.baseUrl, '/api/admin/invites', {
      method: 'POST',
      cookie: admin,
      body: {},
    })
    assert.equal(created.status, 201)
    const invite = created.body as { code: string; expires_at: string }
    assert.ok(invite.code)
    const expiresInDays = (Date.parse(invite.expires_at) - Date.now()) / 86_400_000
    assert.ok(Math.abs(expiresInDays - 7) < 0.01)

    const invalid = await api(context.baseUrl, '/api/admin/invites', {
      method: 'POST',
      cookie: admin,
      body: { expires_in_seconds: 1 },
    })
    assert.equal(invalid.status, 400)
  })

  it('admin 可列出邀请码及其状态', async () => {
    const admin = await adminCookie()
    await api(context.baseUrl, '/api/admin/invites', {
      method: 'POST',
      cookie: admin,
      body: { expires_in_seconds: 3600 },
    })
    const listed = await api(context.baseUrl, '/api/admin/invites', { cookie: admin })
    assert.equal(listed.status, 200)
    const invites = (listed.body as { invites: InviteItem[] }).invites
    assert.equal(invites.length, 1)
    assert.equal(invites[0]?.status, 'unused')
  })

  it('作废邀请码后无法注册，作废不存在的邀请码返回 404', async () => {
    const admin = await adminCookie()
    const created = await api(context.baseUrl, '/api/admin/invites', {
      method: 'POST',
      cookie: admin,
      body: { expires_in_seconds: 3600 },
    })
    const code = (created.body as { code: string }).code

    const revoked = await api(context.baseUrl, `/api/admin/invites/${code}`, {
      method: 'DELETE',
      cookie: admin,
    })
    assert.equal(revoked.status, 204)

    const registered = await api(context.baseUrl, '/api/auth/register', {
      method: 'POST',
      body: { username: 'alice', password: 'password123', invite_code: code },
    })
    assert.equal(registered.status, 400)

    const missing = await api(context.baseUrl, '/api/admin/invites/does-not-exist', {
      method: 'DELETE',
      cookie: admin,
    })
    assert.equal(missing.status, 404)
  })

  it('admin 可查看用户列表并提权，提权幂等', async () => {
    const userCookie = await createUserViaRegister('bob')
    const admin = await adminCookie()

    const usersResponse = await api(context.baseUrl, '/api/admin/users', { cookie: admin })
    assert.equal(usersResponse.status, 200)
    const users = (usersResponse.body as { users: UserItem[] }).users
    const bob = users.find((user) => user.username === 'bob')
    assert.ok(bob)
    assert.equal(bob.role, 'user')

    const promoted = await api(context.baseUrl, `/api/admin/users/${bob.id}/promote`, {
      method: 'POST',
      cookie: admin,
    })
    assert.equal(promoted.status, 200)
    assert.equal((promoted.body as { user: UserItem }).user.role, 'admin')

    const promotedAgain = await api(context.baseUrl, `/api/admin/users/${bob.id}/promote`, {
      method: 'POST',
      cookie: admin,
    })
    assert.equal(promotedAgain.status, 200)
    assert.equal((promotedAgain.body as { user: UserItem }).user.role, 'admin')

    const meAfterPromotion = await api(context.baseUrl, '/api/auth/me', { cookie: userCookie })
    assert.equal(meAfterPromotion.status, 200)
    assert.equal((meAfterPromotion.body as { user: UserItem }).user.role, 'admin')
  })

  it('提权不存在的用户返回 404', async () => {
    const admin = await adminCookie()
    const response = await api(context.baseUrl, '/api/admin/users/no-such-id/promote', {
      method: 'POST',
      cookie: admin,
    })
    assert.equal(response.status, 404)
  })

  it('普通用户访问 admin 端点全部返回 403', async () => {
    const userCookie = await createUserViaRegister('carol')
    const paths = [
      ['/api/admin/invites', 'POST'],
      ['/api/admin/invites', 'GET'],
      ['/api/admin/invites/any', 'DELETE'],
      ['/api/admin/users', 'GET'],
      ['/api/admin/users/any/promote', 'POST'],
    ] as const
    for (const [path, method] of paths) {
      const response = await api(context.baseUrl, path, {
        method,
        cookie: userCookie,
        body: method === 'POST' ? {} : undefined,
      })
      assert.equal(response.status, 403, `${method} ${path} should be 403`)
      assert.equal((response.body as { error: { code: string } }).error.code, 'FORBIDDEN')
    }
  })
})
