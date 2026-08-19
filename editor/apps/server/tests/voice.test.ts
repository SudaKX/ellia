import assert from 'node:assert/strict'
import { after, before, describe, it } from 'node:test'

import { api, createProject, loginCookie, startTestServer, type TestContext } from './helpers.js'

describe('voice API', () => {
  let ctx: TestContext
  let cookie: string
  let projectId: string

  before(async () => {
    ctx = await startTestServer()
    cookie = await loginCookie(ctx.baseUrl)
    projectId = (await createProject(ctx.baseUrl, cookie, 'voice-module')).id
  })

  after(async () => {
    await ctx.close()
  })

  it('未登录访问语音频道端点返回 401', async () => {
    const response = await api(ctx.baseUrl, `/api/projects/${projectId}/voice/channels`)
    assert.equal(response.status, 401)
  })

  it('创建频道成功并出现在列表中', async () => {
    const created = await api(ctx.baseUrl, `/api/projects/${projectId}/voice/channels`, {
      method: 'POST',
      cookie,
      body: { name: '大厅' },
    })
    assert.equal(created.status, 201)
    const channel = (created.body as { channel: Record<string, unknown> }).channel
    assert.equal(channel.name, '大厅')
    assert.equal(channel.max_participants, 8)
    assert.equal(channel.participant_count, 0)

    const listed = await api(ctx.baseUrl, `/api/projects/${projectId}/voice/channels`, { cookie })
    assert.equal(listed.status, 200)
    const channels = (listed.body as { channels: Array<{ id: string; name: string }> }).channels
    assert.equal(channels.length, 1)
    assert.equal(channels[0].id, channel.id)
  })

  it('项目内同名频道返回 409', async () => {
    const response = await api(ctx.baseUrl, `/api/projects/${projectId}/voice/channels`, {
      method: 'POST',
      cookie,
      body: { name: '大厅' },
    })
    assert.equal(response.status, 409)
    assert.deepEqual((response.body as { error: { code: string } }).error.code, 'RESOURCE_CONFLICT')
  })

  it('删除频道后列表为空', async () => {
    const listed = await api(ctx.baseUrl, `/api/projects/${projectId}/voice/channels`, { cookie })
    const channels = (listed.body as { channels: Array<{ id: string }> }).channels
    assert.ok(channels.length > 0)
    const channelId = channels[0]!.id

    const deleted = await api(
      ctx.baseUrl,
      `/api/projects/${projectId}/voice/channels/${channelId}`,
      { method: 'DELETE', cookie },
    )
    assert.equal(deleted.status, 204)

    const afterDelete = await api(ctx.baseUrl, `/api/projects/${projectId}/voice/channels`, { cookie })
    assert.equal((afterDelete.body as { channels: unknown[] }).channels.length, 0)
  })

  it('不存在的项目创建频道返回 404', async () => {
    const response = await api(ctx.baseUrl, '/api/projects/does-not-exist/voice/channels', {
      method: 'POST',
      cookie,
      body: { name: '无效' },
    })
    assert.equal(response.status, 404)
    assert.deepEqual((response.body as { error: { code: string } }).error.code, 'PROJECT_NOT_FOUND')
  })
})
