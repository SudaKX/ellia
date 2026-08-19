import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { after, before, describe, it } from 'node:test'

import {
  createProject,
  loginCookie,
  startTestServerWithWs,
  wsConnect,
  type TestContext,
  type WsTestClient,
} from './helpers.js'
import { getDatabase } from '../src/db/database.js'

describe('files API', () => {
  let ctx: TestContext
  let cookie: string
  let fileDir: string
  let admin: WsTestClient

  before(async () => {
    fileDir = mkdtempSync(join(tmpdir(), 'ellia-files-test-'))
    ctx = await startTestServerWithWs({ fileDataDir: fileDir, maxFileBytes: 1024 })
    cookie = await loginCookie(ctx.baseUrl)
    const projectId = (await createProject(ctx.baseUrl, cookie, 'file-lab')).id
    admin = await wsConnect(ctx.wsUrl, cookie, projectId)
    await admin.waitFor('hello')
  })

  after(async () => {
    await admin.close().catch(() => undefined)
    await ctx.close()
    rmSync(fileDir, { recursive: true, force: true })
  })

  async function upload(
    bytes: Uint8Array,
    headers: Record<string, string> = {},
    withCookie = true,
  ): Promise<{ status: number; body: Record<string, unknown> }> {
    const requestHeaders = new Headers(headers)
    if (withCookie) requestHeaders.set('cookie', cookie)
    const response = await fetch(`${ctx.baseUrl}/api/files`, {
      method: 'POST',
      headers: requestHeaders,
      body: bytes as BodyInit,
    })
    const text = await response.text()
    let body: Record<string, unknown> = {}
    try {
      body = JSON.parse(text) as Record<string, unknown>
    } catch {
      body = { raw: text }
    }
    return { status: response.status, body }
  }

  async function download(fileId: string, withCookie = true): Promise<Response> {
    const headers = new Headers()
    if (withCookie) headers.set('cookie', cookie)
    return fetch(`${ctx.baseUrl}/api/files/${fileId}`, { headers })
  }

  async function list(withCookie = true): Promise<Response> {
    const headers = new Headers()
    if (withCookie) headers.set('cookie', cookie)
    return fetch(`${ctx.baseUrl}/api/files`, { headers })
  }

  async function createAssetViaWs(fileId: string, resourceId: string) {
    const requestRef = Math.random().toString(36).slice(2)
    admin.send({
      type: 'create',
      ref: requestRef,
      group: 'main',
      kind: 'asset',
      ui_kind: 'asset',
      resource_id: resourceId,
      state: { file_id: fileId, media_type: 'text/plain' },
    })
    const created = await admin.waitFor(
      'created',
      2000,
      (message) => message.ref === requestRef,
    )
    return created.entity as { id: string }
  }

  it('未登录上传返回 401', async () => {
    const result = await upload(new Uint8Array([1]), {}, false)
    assert.equal(result.status, 401)
  })

  it('列表返回全部文件且按 created_at 降序', async () => {
    const first = await upload(new TextEncoder().encode('first'), {
      'content-type': 'text/plain',
      'x-original-name': 'first.txt',
    })
    await new Promise((resolve) => setTimeout(resolve, 30))
    const second = await upload(new TextEncoder().encode('second'), {
      'content-type': 'text/plain',
      'x-original-name': 'second.txt',
    })
    const response = await list()
    assert.equal(response.status, 200)
    const body = (await response.json()) as {
      files: Array<{ file_id: string; original_name: string | null }>
    }
    assert.ok(Array.isArray(body.files))
    assert.ok(body.files.length >= 2)
    const firstIndex = body.files.findIndex((file) => file.file_id === first.body.file_id)
    const secondIndex = body.files.findIndex((file) => file.file_id === second.body.file_id)
    assert.notEqual(firstIndex, -1)
    assert.notEqual(secondIndex, -1)
    assert.ok(secondIndex < firstIndex)
  })

  it('未登录文件列表返回 401', async () => {
    const response = await list(false)
    assert.equal(response.status, 401)
    assert.equal(
      ((await response.json()) as { error: { code: string } }).error.code,
      'UNAUTHORIZED',
    )
  })

  it('上传成功：元数据、sha256 与磁盘内容一致', async () => {
    const bytes = new TextEncoder().encode('hello world')
    const expectedSha = createHash('sha256').update(bytes).digest('hex')
    const result = await upload(bytes, {
      'content-type': 'text/plain',
      'x-original-name': 'readme.txt',
    })
    assert.equal(result.status, 201)
    const fileId = result.body.file_id as string
    assert.equal(result.body.original_name, 'readme.txt')
    assert.equal(result.body.media_type, 'text/plain')
    assert.equal(result.body.size, bytes.length)
    assert.equal(result.body.sha256, expectedSha)

    const diskPath = join(fileDir, fileId)
    assert.ok(existsSync(diskPath))
    assert.deepEqual(readFileSync(diskPath), Buffer.from(bytes))
  })

  it('中文文件名通过 base64 头传递并正确保存', async () => {
    const originalName = '中文文件.txt'
    const bytes = new TextEncoder().encode('中文内容')
    const result = await upload(bytes, {
      'content-type': 'text/plain; charset=utf-8',
      'x-original-name-base64': Buffer.from(originalName, 'utf8').toString('base64'),
    })
    assert.equal(result.status, 201)
    assert.equal(result.body.original_name, originalName)
  })

  it('下载返回原始字节与元数据头', async () => {
    const bytes = new TextEncoder().encode('download me')
    const expectedSha = createHash('sha256').update(bytes).digest('hex')
    const uploaded = await upload(bytes, {
      'content-type': 'text/plain; charset=utf-8',
      'x-original-name': 'dl.txt',
    })
    const fileId = uploaded.body.file_id as string

    const response = await download(fileId)
    assert.equal(response.status, 200)
    assert.equal(response.headers.get('content-type'), 'text/plain')
    assert.equal(response.headers.get('x-original-name'), 'dl.txt')
    assert.equal(response.headers.get('x-file-sha256'), expectedSha)
    assert.equal(response.headers.get('x-file-size'), String(bytes.length))
    assert.deepEqual(Buffer.from(await response.arrayBuffer()), Buffer.from(bytes))
  })

  it('超过 MAX_FILE_BYTES 返回 413 FILE_TOO_LARGE', async () => {
    const result = await upload(new Uint8Array(2048), { 'content-type': 'application/octet-stream' })
    assert.equal(result.status, 413)
    assert.equal(
      (result.body as { error?: { code: string } }).error?.code,
      'FILE_TOO_LARGE',
    )
  })

  it('下载与删除不存在的文件返回 404', async () => {
    const missing = '00000000-0000-4000-8000-000000000000'
    const downloadResponse = await download(missing)
    assert.equal(downloadResponse.status, 404)
    assert.equal(
      ((await downloadResponse.json()) as { error: { code: string } }).error.code,
      'FILE_NOT_FOUND',
    )

    const deleteResponse = await fetch(`${ctx.baseUrl}/api/files/${missing}`, {
      method: 'DELETE',
      headers: { cookie },
    })
    assert.equal(deleteResponse.status, 404)
  })

  it('手动删除无条件生效：被 asset 引用也删除，悬空允许', async () => {
    const uploaded = await upload(new TextEncoder().encode('referenced'), {
      'content-type': 'text/plain',
    })
    const fileId = uploaded.body.file_id as string
    const asset = await createAssetViaWs(fileId, 'asset-path:assets/referenced.txt')

    const deleteResponse = await fetch(`${ctx.baseUrl}/api/files/${fileId}`, {
      method: 'DELETE',
      headers: { cookie },
    })
    assert.equal(deleteResponse.status, 204)
    assert.ok(!existsSync(join(fileDir, fileId)))

    const row = getDatabase()
      .prepare('SELECT state FROM entities WHERE id = ?')
      .get(asset.id) as { state: string }
    assert.equal((JSON.parse(row.state) as { file_id: string }).file_id, fileId)
  })

  it('上传不改变任何实体的 revision/version', async () => {
    const requestRef = Math.random().toString(36).slice(2)
    admin.send({
      type: 'create',
      ref: requestRef,
      group: 'main',
      kind: 'hint',
      ui_kind: 'form',
      resource_id: 'hint:stable-entity',
      state: {
        stable_id: 'stable-entity',
        source_asset_id: 'asset-path:assets/hint.txt',
        download_name: 'hint.txt',
        credit_id: 'credit-id:vib',
        credit_amount: 1,
        display: { title: '稳定实体' },
      },
    })
    const created = await admin.waitFor(
      'created',
      2000,
      (message) => message.ref === requestRef,
    )
    const entityId = (created.entity as { id: string }).id
    const before = getDatabase()
      .prepare('SELECT revision, version FROM entities WHERE id = ?')
      .get(entityId) as { revision: number; version: number }

    await upload(new TextEncoder().encode('upload does not touch entities'), {
      'content-type': 'text/plain',
    })

    const afterUpload = getDatabase()
      .prepare('SELECT revision, version FROM entities WHERE id = ?')
      .get(entityId) as { revision: number; version: number }
    assert.deepEqual(afterUpload, before)
  })
})
