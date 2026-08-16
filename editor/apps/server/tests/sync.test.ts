import assert from 'node:assert/strict'
import { once } from 'node:events'
import { after, before, describe, it } from 'node:test'

import WebSocket from 'ws'

import {
  createProject,
  loginCookie,
  startTestServerWithWs,
  wsConnect,
  type TestContext,
  type WsTestClient,
} from './helpers.js'

describe('WS v2 sync', () => {
  let ctx: TestContext
  let cookie: string
  let projectId: string
  let admin: WsTestClient
  const clients: WsTestClient[] = []

  before(async () => {
    ctx = await startTestServerWithWs()
    cookie = await loginCookie(ctx.baseUrl)
    projectId = (await createProject(ctx.baseUrl, cookie, 'sync-lab')).id
    admin = await connect()
  })

  after(async () => {
    for (const client of clients) await client.close().catch(() => undefined)
    await ctx.close()
  })

  async function connect(): Promise<WsTestClient> {
    const client = await wsConnect(ctx.wsUrl, cookie, projectId)
    clients.push(client)
    await client.waitFor('hello')
    return client
  }

  function ref(): string {
    return Math.random().toString(36).slice(2)
  }

  async function createHint(client: WsTestClient, resourceId: string, title = '初始标题') {
    const requestRef = ref()
    client.send({
      type: 'create',
      ref: requestRef,
      group: 'main',
      kind: 'hint',
      ui_kind: 'form',
      resource_id: resourceId,
      state: {
        stable_id: resourceId.slice('stable-id:'.length),
        credit_id: 'vib',
        credit_amount: 1,
        display: { title },
      },
    })
    const created = await client.waitFor('created')
    assert.equal(created.ref, requestRef)
    return created.entity as { id: string; resource_id: string; revision: number; version: number }
  }

  it('未登录与项目不存在时拒绝 WS 升级', async () => {
    const noCookie = new WebSocket(
      `${ctx.wsUrl}/ws/projects/${encodeURIComponent(projectId)}`,
    )
    const [, noCookieRes] = await once(noCookie, 'unexpected-response')
    assert.equal((noCookieRes as { statusCode: number }).statusCode, 401)

    const missingProject = new WebSocket(
      `${ctx.wsUrl}/ws/projects/does-not-exist`,
      { headers: { Cookie: cookie } },
    )
    const [, missingRes] = await once(missingProject, 'unexpected-response')
    assert.equal((missingRes as { statusCode: number }).statusCode, 404)
  })

  it('join 全量 diff、增量一致与 removed_ids', async () => {
    const hint = await createHint(admin, 'stable-id:join-1')
    const other = await connect()
    other.send({ type: 'join', project_id: projectId, vector: {} })
    const full = await other.waitFor('sync')
    assert.equal((full.entities as unknown[]).length, 1)

    other.send({ type: 'join', project_id: projectId, vector: { [hint.id]: hint.revision } })
    const incremental = await other.waitFor('sync')
    assert.equal((incremental.entities as unknown[]).length, 0)
    assert.equal((incremental.removed_ids as unknown[]).length, 0)

    admin.send({ type: 'delete', ref: ref(), entity_id: hint.id })
    await admin.waitFor('deleted')
    other.send({ type: 'join', project_id: projectId, vector: { [hint.id]: hint.revision } })
    const removed = await other.waitFor('sync')
    assert.deepEqual(removed.removed_ids, [hint.id])
    assert.equal((removed.entities as unknown[]).length, 0)
    await other.close()
  })

  it('create 广播到房间其他连接', async () => {
    const other = await connect()
    other.send({ type: 'join', project_id: projectId, vector: {} })
    await other.waitFor('sync')
    const createdPromise = other.waitFor('created')
    const hint = await createHint(admin, 'stable-id:broadcast-1')
    const broadcast = await createdPromise
    assert.equal((broadcast.entity as { id: string }).id, hint.id)
    await other.close()
  })

  it('lock/patch：applied 给提交者，update+unlocked 广播给他人', async () => {
    const hint = await createHint(admin, 'stable-id:patch-1')
    const other = await connect()
    const dataPath = `${hint.id}@state:/display/title`
    admin.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: dataPath })
    await admin.waitFor('locked')

    admin.send({
      type: 'patch',
      ref: 'patch-1',
      entity_id: hint.id,
      data_path: dataPath,
      value: '新标题',
    })
    const applied = await admin.waitFor('applied')
    assert.equal(applied.ref, 'patch-1')
    assert.equal(applied.revision, 2)
    assert.equal(applied.version, 2)

    const update = await other.waitFor('update')
    assert.equal(update.entity_id, hint.id)
    assert.equal(update.data_path, dataPath)
    assert.equal(update.value, '新标题')
    const unlocked = await other.waitFor('unlocked')
    assert.equal(unlocked.data_path, dataPath)
    await other.close()
  })

  it('锁冲突返回 lock_denied，未持锁 patch 返回 STALE_LOCK', async () => {
    const hint = await createHint(admin, 'stable-id:lock-1')
    const other = await connect()
    const dataPath = `${hint.id}@state:/display/title`

    admin.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: dataPath })
    await admin.waitFor('locked')

    other.send({ type: 'lock', ref: 'lock-b', entity_id: hint.id, data_path: dataPath })
    const denied = await other.waitFor('lock_denied')
    assert.equal(denied.ref, 'lock-b')
    assert.equal((denied.holder as { username: string }).username, 'admin')

    other.send({
      type: 'patch',
      ref: 'stale',
      entity_id: hint.id,
      data_path: dataPath,
      value: '抢写',
    })
    const error = await other.waitFor('error')
    assert.equal(error.code, 'STALE_LOCK')

    admin.send({ type: 'unlock', ref: ref(), entity_id: hint.id, data_path: dataPath })
    await admin.waitFor('unlocked')
    await other.close()
  })

  it('同连接锁幂等且新锁顶替旧锁', async () => {
    const hint = await createHint(admin, 'stable-id:lock-2')
    const other = await connect()
    const pathA = `${hint.id}@state:/display/title`
    const pathB = `${hint.id}@group:`

    admin.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: pathA })
    await admin.waitFor('locked')
    admin.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: pathA })
    await admin.waitFor('locked')

    admin.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: pathB })
    await admin.waitFor('locked')
    const unlockedA = await other.waitFor('unlocked')
    assert.equal(unlockedA.data_path, pathA)
    await other.close()
  })

  it('断线释放该连接全部锁', async () => {
    const hint = await createHint(admin, 'stable-id:lock-3')
    const other = await connect()
    const dataPath = `${hint.id}@state:/display/title`

    other.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: dataPath })
    await other.waitFor('locked')
    const unlockedPromise = admin.waitFor('unlocked', 2000, (message) => message.data_path === dataPath)
    await other.close()
    const unlocked = await unlockedPromise
    assert.equal(unlocked.data_path, dataPath)

    admin.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: dataPath })
    await admin.waitFor('locked')
    admin.send({ type: 'unlock', ref: ref(), entity_id: hint.id, data_path: dataPath })
    await admin.waitFor('unlocked')
  })

  it('group 与 resource_id 的 patch 规则', async () => {
    const hint = await createHint(admin, 'stable-id:meta-1')

    const groupPath = `${hint.id}@group:`
    admin.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: groupPath })
    await admin.waitFor('locked')
    admin.send({ type: 'patch', ref: 'g', entity_id: hint.id, data_path: groupPath, value: 'chapter1' })
    const groupApplied = await admin.waitFor('applied')
    assert.equal(groupApplied.version, 2)

    const resourcePath = `${hint.id}@resource_id:`
    admin.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: resourcePath })
    await admin.waitFor('locked')
    admin.send({
      type: 'patch',
      ref: 'r',
      entity_id: hint.id,
      data_path: resourcePath,
      value: 'stable-id:meta-1-renamed',
    })
    const renamed = await admin.waitFor('applied')
    assert.equal(renamed.version, 3)

    admin.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: resourcePath })
    await admin.waitFor('locked')
    admin.send({
      type: 'patch',
      ref: 'bad',
      entity_id: hint.id,
      data_path: resourcePath,
      value: 'account-id:wrong',
    })
    const error = await admin.waitFor('error')
    assert.equal(error.code, 'VALIDATION')
  })

  it('删除：他人锁拒绝 ENTITY_LOCKED；删除后可同 resource_id 重建', async () => {
    const hint = await createHint(admin, 'stable-id:delete-1')
    const other = await connect()
    const dataPath = `${hint.id}@state:/display/title`

    other.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: dataPath })
    await other.waitFor('locked')
    admin.send({ type: 'delete', ref: 'del', entity_id: hint.id })
    const denied = await admin.waitFor('error')
    assert.equal(denied.code, 'ENTITY_LOCKED')

    other.send({ type: 'unlock', ref: ref(), entity_id: hint.id, data_path: dataPath })
    await other.waitFor('unlocked')

    admin.send({ type: 'delete', ref: 'del', entity_id: hint.id })
    const deleted = await admin.waitFor('deleted')
    assert.equal(deleted.entity_id, hint.id)

    admin.send({ type: 'patch', ref: 'gone', entity_id: hint.id, data_path: dataPath, value: 'x' })
    const notFound = await admin.waitFor('error')
    assert.equal(notFound.code, 'ENTITY_NOT_FOUND')

    const rebuilt = await createHint(admin, 'stable-id:delete-1')
    assert.notEqual(rebuilt.id, hint.id)
    await other.close()
  })

  it('rollback 应用 v-1 快照、version 递减、revision 递增', async () => {
    const hint = await createHint(admin, 'stable-id:rollback-1', '旧标题')
    const other = await connect()
    const dataPath = `${hint.id}@state:/display/title`

    admin.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: dataPath })
    await admin.waitFor('locked')
    admin.send({ type: 'patch', ref: 'p', entity_id: hint.id, data_path: dataPath, value: '新标题' })
    await admin.waitFor('applied')

    const rolledPromise = other.waitFor('rolled_back')
    admin.send({ type: 'rollback', ref: 'rb', entity_id: hint.id })
    const rolled = await rolledPromise
    assert.equal(rolled.version, 1)
    assert.equal(rolled.revision, 3)
    assert.equal((rolled.state as { display: { title: string } }).display.title, '旧标题')
    await other.close()
  })

  it('无历史回退返回 HISTORY_EMPTY', async () => {
    const hint = await createHint(admin, 'stable-id:rollback-2')
    admin.send({ type: 'rollback', ref: 'rb', entity_id: hint.id })
    const error = await admin.waitFor('error')
    assert.equal(error.code, 'HISTORY_EMPTY')
  })

  it('history 按 version 降序返回', async () => {
    const hint = await createHint(admin, 'stable-id:history-1')
    const dataPath = `${hint.id}@state:/display/title`
    for (const value of ['v2', 'v3']) {
      admin.send({ type: 'lock', ref: ref(), entity_id: hint.id, data_path: dataPath })
      await admin.waitFor('locked')
      admin.send({ type: 'patch', ref: ref(), entity_id: hint.id, data_path: dataPath, value })
      await admin.waitFor('applied')
    }
    admin.send({ type: 'history', ref: 'h', entity_id: hint.id })
    const history = await admin.waitFor('history')
    const entries = history.entries as Array<{ version: number }>
    assert.deepEqual(entries.map((entry) => entry.version), [2, 1])
  })

  it('focus 广播 presence，断开后清除位置', async () => {
    const hint = await createHint(admin, 'stable-id:focus-1')
    const other = await connect()
    admin.flush('presence')
    other.send({
      type: 'focus',
      entity_id: hint.id,
      data_path: `${hint.id}@state:/display/title`,
    })
    const presence = await admin.waitFor(
      'presence',
      2000,
      (message) =>
        (message.users as Array<Record<string, unknown>>).some(
          (entry) => entry.entity_id === hint.id,
        ),
    )
    const user = (presence.users as Array<Record<string, unknown>>).find(
      (entry) => entry.entity_id === hint.id,
    )
    assert.ok(user)

    admin.flush('presence')
    const clearedPromise = admin.waitFor(
      'presence',
      2000,
      (message) =>
        (message.users as Array<Record<string, unknown>>).every(
          (entry) => entry.entity_id === undefined,
        ),
    )
    await other.close()
    const cleared = await clearedPromise
    for (const entry of cleared.users as Array<Record<string, unknown>>) {
      assert.equal(entry.entity_id, undefined)
    }
  })

  it('ping/pong 与 BAD_JSON', async () => {
    admin.send({ type: 'ping' })
    const pong = await admin.waitFor('pong')
    assert.equal(pong.type, 'pong')

    admin.ws.send('not-json')
    const error = await admin.waitFor('error')
    assert.equal(error.code, 'BAD_JSON')
  })

  it('asset 悬空 file_id、共享 file_id 与 file_id patch 回退', async () => {
    const fileId = '00000000-0000-4000-8000-000000000001'
    const createdA = await createEntityWs('asset', 'asset-path:assets/a.txt', {
      file_id: fileId,
      media_type: 'text/plain',
    })
    const createdB = await createEntityWs('asset', 'asset-path:assets/b.txt', {
      file_id: fileId,
      media_type: 'text/plain',
    })
    assert.equal(
      (createdB.entity as { state: { file_id: string } }).state.file_id,
      (createdA.entity as { state: { file_id: string } }).state.file_id,
    )

    const entityId = (createdA.entity as { id: string }).id
    const dataPath = `${entityId}@state:/file_id`
    admin.send({ type: 'lock', ref: ref(), entity_id: entityId, data_path: dataPath })
    await admin.waitFor('locked')
    admin.send({
      type: 'patch',
      ref: 'f',
      entity_id: entityId,
      data_path: dataPath,
      value: '00000000-0000-4000-8000-000000000002',
    })
    await admin.waitFor('applied', 2000, (message) => message.ref === 'f')

    admin.send({ type: 'rollback', ref: 'rbf', entity_id: entityId })
    const rolled = await admin.waitFor(
      'rolled_back',
      2000,
      (message) => message.entity_id === entityId,
    )
    assert.equal((rolled.state as { file_id: string }).file_id, fileId)
  })

  it('file-tree / progress-dag 容器整容器加锁 patch', async () => {
    const tree = await createEntityWs('file-tree', 'file-tree:main', {
      root_stable_id: null,
      children: {},
    })
    const treeId = (tree.entity as { id: string }).id
    const treePath = `${treeId}@state:/children`
    admin.send({ type: 'lock', ref: ref(), entity_id: treeId, data_path: treePath })
    await admin.waitFor('locked')
    admin.send({
      type: 'patch',
      ref: 't',
      entity_id: treeId,
      data_path: treePath,
      value: { dir: ['file-a'] },
    })
    const applied = await admin.waitFor('applied')
    assert.equal(applied.revision, 2)

    const dag = await createEntityWs('progress-dag', 'progress-dag:main', {
      entry_stable_ids: ['start'],
      successors: { start: ['end'] },
    })
    const dagId = (dag.entity as { id: string }).id
    const dagPath = `${dagId}@state:/successors`
    admin.send({ type: 'lock', ref: ref(), entity_id: dagId, data_path: dagPath })
    await admin.waitFor('locked')
    admin.send({
      type: 'patch',
      ref: 'd',
      entity_id: dagId,
      data_path: dagPath,
      value: { start: ['end', 'bonus'] },
    })
    await admin.waitFor('applied')
  })

  async function createEntityWs(
    kind: string,
    resourceId: string,
    state: unknown,
  ): Promise<Record<string, unknown>> {
    const requestRef = ref()
    admin.send({
      type: 'create',
      ref: requestRef,
      group: 'main',
      kind,
      ui_kind: kind === 'asset' ? 'asset' : kind === 'file-tree' ? 'file-tree' : 'progress-dag',
      resource_id: resourceId,
      state,
    })
    const created = await admin.waitFor('created')
    assert.equal(created.ref, requestRef)
    return created
  }
})
