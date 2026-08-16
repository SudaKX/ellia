import assert from 'node:assert/strict'
import { after, before, describe, it } from 'node:test'

import { api, loginCookie, startTestServer, type TestContext } from './helpers.js'

describe('projects API', () => {
  let ctx: TestContext
  let cookie: string

  before(async () => {
    ctx = await startTestServer()
    cookie = await loginCookie(ctx.baseUrl)
  })

  after(async () => {
    await ctx.close()
  })

  it('未登录访问项目端点返回 401', async () => {
    const response = await api(ctx.baseUrl, '/api/projects')
    assert.equal(response.status, 401)
    assert.deepEqual((response.body as { error: { code: string } }).error.code, 'UNAUTHORIZED')
  })

  it('创建项目成功且返回完整字段', async () => {
    const response = await api(ctx.baseUrl, '/api/projects', {
      method: 'POST',
      cookie,
      body: { module_id: 'example2', display_name: '示例模块' },
    })
    assert.equal(response.status, 201)
    const project = (response.body as { project: Record<string, unknown> }).project
    assert.equal(project.module_id, 'example2')
    assert.equal(project.display_name, '示例模块')
    assert.equal(project.description, null)
    assert.equal(project.deploy_baseline, null)
    assert.equal(typeof project.id, 'string')
    assert.equal(typeof project.created_at, 'string')
    assert.equal(typeof project.updated_at, 'string')
  })

  it('module_id 重复返回 409', async () => {
    await api(ctx.baseUrl, '/api/projects', {
      method: 'POST',
      cookie,
      body: { module_id: 'dup', display_name: '第一次' },
    })
    const response = await api(ctx.baseUrl, '/api/projects', {
      method: 'POST',
      cookie,
      body: { module_id: 'dup', display_name: '第二次' },
    })
    assert.equal(response.status, 409)
    assert.deepEqual((response.body as { error: { code: string } }).error.code, 'RESOURCE_CONFLICT')
  })

  it('非法 module_id 返回 400', async () => {
    for (const moduleId of ['', '.', '..', 'a/b', 'a\\b']) {
      const response = await api(ctx.baseUrl, '/api/projects', {
        method: 'POST',
        cookie,
        body: { module_id: moduleId, display_name: '非法' },
      })
      assert.equal(response.status, 400, `module_id=${JSON.stringify(moduleId)}`)
      assert.deepEqual((response.body as { error: { code: string } }).error.code, 'VALIDATION')
    }
  })

  it('列表按 updated_at 降序返回', async () => {
    const createA = await api(ctx.baseUrl, '/api/projects', {
      method: 'POST',
      cookie,
      body: { module_id: 'order-a', display_name: 'A' },
    })
    const createB = await api(ctx.baseUrl, '/api/projects', {
      method: 'POST',
      cookie,
      body: { module_id: 'order-b', display_name: 'B' },
    })
    const idA = (createA.body as { project: { id: string } }).project.id
    const idB = (createB.body as { project: { id: string } }).project.id

    await new Promise((resolve) => setTimeout(resolve, 5))
    await api(ctx.baseUrl, `/api/projects/${idA}`, {
      method: 'PATCH',
      cookie,
      body: { display_name: 'A 更新' },
    })

    const list = await api(ctx.baseUrl, '/api/projects', { cookie })
    const projects = (list.body as { projects: Array<{ id: string }> }).projects
    assert.equal(projects[0].id, idA)
    assert.ok(projects.some((project) => project.id === idB))
  })

  it('项目详情不存在返回 404', async () => {
    const response = await api(ctx.baseUrl, '/api/projects/does-not-exist', { cookie })
    assert.equal(response.status, 404)
    assert.deepEqual((response.body as { error: { code: string } }).error.code, 'PROJECT_NOT_FOUND')
  })

  it('PATCH 更新字段并刷新 updated_at', async () => {
    const create = await api(ctx.baseUrl, '/api/projects', {
      method: 'POST',
      cookie,
      body: { module_id: 'patch-me', display_name: '旧名' },
    })
    const project = (create.body as { project: { id: string; updated_at: string } }).project

    await new Promise((resolve) => setTimeout(resolve, 5))
    const response = await api(ctx.baseUrl, `/api/projects/${project.id}`, {
      method: 'PATCH',
      cookie,
      body: { display_name: '新名', deploy_baseline: 'register_all()' },
    })
    assert.equal(response.status, 200)
    const updated = (response.body as { project: { updated_at: string } }).project
    assert.equal(
      (response.body as { project: { display_name: string } }).project.display_name,
      '新名',
    )
    assert.ok(updated.updated_at > project.updated_at)
  })

  it('PATCH 携带 module_id 返回 400 且原值不变', async () => {
    const create = await api(ctx.baseUrl, '/api/projects', {
      method: 'POST',
      cookie,
      body: { module_id: 'immutable', display_name: '不可改' },
    })
    const project = (create.body as { project: { id: string } }).project
    const response = await api(ctx.baseUrl, `/api/projects/${project.id}`, {
      method: 'PATCH',
      cookie,
      body: { module_id: 'renamed' },
    })
    assert.equal(response.status, 400)
    const detail = await api(ctx.baseUrl, `/api/projects/${project.id}`, { cookie })
    assert.equal(
      (detail.body as { project: { module_id: string } }).project.module_id,
      'immutable',
    )
  })
})
