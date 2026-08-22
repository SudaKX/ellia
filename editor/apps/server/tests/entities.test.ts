import assert from 'node:assert/strict'
import { after, before, beforeEach, describe, it } from 'node:test'

import { seedInitialAdmin } from '../src/auth/users.js'
import { testConfig } from './helpers.js'
import { closeDatabase, getDatabase, initDatabase } from '../src/db/database.js'
import { ensureMetaSeeded } from '../src/db/meta.js'
import { ApiError } from '../src/errors.js'
import { createProject } from '../src/services/projects.js'
import {
  createEntity,
  deleteEntity,
  listHistory,
  patchEntity,
  requireEntity,
  rollbackEntity,
} from '../src/services/entities.js'

describe('entities service', () => {
  let projectId: string
  let adminId: string

  before(async () => {
    initDatabase(':memory:')
    const config = testConfig()
    await seedInitialAdmin(getDatabase(), config)
    ensureMetaSeeded(config)
    const row = getDatabase()
      .prepare('SELECT id FROM users WHERE username = ?')
      .get(config.adminUsername) as { id: string }
    adminId = row.id
    projectId = createProject(
      { module_id: 'entity-lab', display_name: '实体测试' },
      adminId,
    ).id
  })

  after(() => {
    closeDatabase()
  })

  beforeEach(() => {
    // 每个用例隔离数据：清理实体
    const db = getDatabase()
    db.prepare('DELETE FROM entities').run()
  })

  function hint(resourceId: string, stableId = resourceId.slice(resourceId.indexOf(':') + 1)) {
    return createEntity(
      projectId,
      {
        kind: 'hint',
        ui_kind: 'form',
        resource_id: resourceId,
        state: {
          stable_id: stableId,
          source_asset_id: 'asset:assets/hint.txt',
          download_name: 'hint.txt',
          credit_id: 'credit:vib',
          credit_amount: 1,
          display: { title: '提示' },
        },
      },
      adminId,
    )
  }

  it('create 初始 revision/version 均为 1', () => {
    const entity = hint('hint:hint-1')
    assert.equal(entity.revision, 1)
    assert.equal(entity.version, 1)
  })

  it('patch 递增 revision 与 version 并写历史', () => {
    const entity = hint('hint:hint-2')
    const updated = patchEntity(
      projectId,
      entity.id,
      `${entity.id}@state:/display/title`,
      '新标题',
      adminId,
    )
    assert.equal(updated.revision, 2)
    assert.equal(updated.version, 2)
    assert.equal(updated.state.display.title, '新标题')
    const history = listHistory(projectId, entity.id)
    assert.equal(history.length, 1)
    assert.equal(history[0].version, 1)
  })

  it('patch set 可创建缺失可选字段，remove 可删除字段', () => {
    const entity = hint('hint:optional-fields')
    const setPath = `${entity.id}@state:/access_rule`
    const set = patchEntity(projectId, entity.id, setPath, 'code:block-1', adminId, 'set')
    assert.equal(set.state.access_rule, 'code:block-1')

    const remove = patchEntity(projectId, entity.id, setPath, undefined, adminId, 'remove')
    assert.equal('access_rule' in remove.state, false)

    assert.throws(
      () => patchEntity(projectId, entity.id, setPath, 'code:block-2', adminId, 'bad' as never),
      (error: unknown) =>
        error instanceof ApiError && error.code === 'VALIDATION' && error.message.includes('op'),
    )
    assert.throws(
      () => patchEntity(projectId, entity.id, `${entity.id}@group:`, undefined, adminId, 'remove'),
      (error: unknown) =>
        error instanceof ApiError && error.code === 'VALIDATION' && error.message.includes('不支持 remove'),
    )
  })

  it('revision 单调且回退后 version 递减', () => {
    const entity = hint('hint:hint-3')
    patchEntity(projectId, entity.id, `${entity.id}@state:/display/title`, 'v2', adminId)
    const v3 = patchEntity(projectId, entity.id, `${entity.id}@state:/display/title`, 'v3', adminId)
    assert.equal(v3.revision, 3)

    const rolled = rollbackEntity(projectId, entity.id, adminId)
    assert.equal(rolled.revision, 4)
    assert.equal(rolled.version, 2)
    assert.equal(rolled.state.display.title, 'v2')
  })

  it('无历史时回退抛 HISTORY_EMPTY', () => {
    const entity = hint('hint:hint-4')
    assert.throws(
      () => rollbackEntity(projectId, entity.id, adminId),
      (error: unknown) =>
        error instanceof ApiError && error.code === 'HISTORY_EMPTY',
    )
  })

  it('历史超过 N 修剪最旧快照', () => {
    const db = getDatabase()
    db.prepare(
      `UPDATE app_meta SET value = '2' WHERE "key" = 'entity_history_limit'`,
    ).run()
    const entity = hint('hint:hint-5')
    for (let index = 0; index < 4; index += 1) {
      patchEntity(
        projectId,
        entity.id,
        `${entity.id}@state:/display/title`,
        `v${index + 2}`,
        adminId,
      )
    }
    const history = listHistory(projectId, entity.id)
    assert.equal(history.length, 2)
    assert.deepEqual(history.map((entry) => entry.version), [4, 3])
    db.prepare(
      `UPDATE app_meta SET value = '20' WHERE "key" = 'entity_history_limit'`,
    ).run()
  })

  it('删除实体级联清除历史，且同 resource_id 可重建', () => {
    const entity = hint('hint:hint-6')
    patchEntity(projectId, entity.id, `${entity.id}@state:/display/title`, '改', adminId)
    assert.equal(deleteEntity(projectId, entity.id), true)
    const db = getDatabase()
    const historyRows = db
      .prepare('SELECT COUNT(*) AS n FROM entity_history WHERE entity_id = ?')
      .get(entity.id) as { n: number }
    assert.equal(historyRows.n, 0)
    const rebuilt = hint('hint:hint-6')
    assert.notEqual(rebuilt.id, entity.id)
    assert.equal(rebuilt.revision, 1)
  })

  it('resource_id 重复创建抛 RESOURCE_CONFLICT', () => {
    hint('hint:hint-7')
    assert.throws(
      () => hint('hint:hint-7'),
      (error: unknown) =>
        error instanceof ApiError && error.code === 'RESOURCE_CONFLICT',
    )
  })

  it('@group patch 合法值生效，非法值抛 VALIDATION', () => {
    const entity = hint('hint:hint-8')
    const updated = patchEntity(
      projectId,
      entity.id,
      `${entity.id}@group:`,
      'chapter1',
      adminId,
    )
    assert.equal(updated.group, 'chapter1')
    assert.throws(
      () => patchEntity(projectId, entity.id, `${entity.id}@group:`, 'Chapter 1!', adminId),
      (error: unknown) =>
        error instanceof ApiError && error.code === 'VALIDATION',
    )
  })

  it('@resource_id patch 保持命名空间，跨命名空间抛 VALIDATION', () => {
    const entity = hint('hint:hint-9')
    const renamed = patchEntity(
      projectId,
      entity.id,
      `${entity.id}@resource_id:`,
      'hint:hint-9-renamed',
      adminId,
    )
    assert.equal(renamed.resource_id, 'hint:hint-9-renamed')
    assert.throws(
      () =>
        patchEntity(
          projectId,
          entity.id,
          `${entity.id}@resource_id:`,
          'account:wrong',
          adminId,
        ),
      (error: unknown) =>
        error instanceof ApiError && error.code === 'VALIDATION',
    )
  })

  it('rollback 恢复 resource_id / comment / group', () => {
    const entity = hint('hint:rollback-meta')
    patchEntity(projectId, entity.id, `${entity.id}@state:/display/title`, 'v2', adminId)
    patchEntity(projectId, entity.id, `${entity.id}@resource_id:`, 'hint:rollback-meta-renamed', adminId)
    patchEntity(projectId, entity.id, `${entity.id}@comment:`, '新注释', adminId)
    patchEntity(projectId, entity.id, `${entity.id}@group:`, 'chapter1', adminId)

    const history = listHistory(projectId, entity.id)
    assert.equal(history[0].version, 4)
    assert.equal(history[0].group, 'main')
    assert.equal(history[0].resource_id, 'hint:rollback-meta-renamed')
    assert.equal(history[0].comment, '新注释')

    let current = rollbackEntity(projectId, entity.id, adminId)
    assert.equal(current.group, 'main')
    assert.equal(current.resource_id, 'hint:rollback-meta-renamed')
    assert.equal(current.comment, '新注释')
    assert.equal(current.state.display.title, 'v2')

    current = rollbackEntity(projectId, entity.id, adminId)
    assert.equal(current.comment, '')
    assert.equal(current.resource_id, 'hint:rollback-meta-renamed')
    assert.equal(current.group, 'main')

    current = rollbackEntity(projectId, entity.id, adminId)
    assert.equal(current.resource_id, 'hint:rollback-meta')
    assert.equal(current.comment, '')
    assert.equal(current.group, 'main')
    assert.equal(current.state.display.title, 'v2')
  })

  it('asset 允许悬空 file_reference，多个 asset 可共享同一 file_reference', () => {
    const a = createEntity(
      projectId,
      {
        kind: 'asset',
        ui_kind: 'asset',
        resource_id: 'asset:a',
        state: {
          file_reference: '00000000-0000-4000-8000-000000000000',
          media_type: 'text/plain',
        },
      },
      adminId,
    )
    const b = createEntity(
      projectId,
      {
        kind: 'asset',
        ui_kind: 'asset',
        resource_id: 'asset:b',
        state: {
          file_reference: '00000000-0000-4000-8000-000000000000',
          media_type: 'text/plain',
        },
      },
      adminId,
    )
    assert.equal(a.state.file_reference, b.state.file_reference)
  })

  it('asset 缺少 media_type 抛 VALIDATION', () => {
    assert.throws(
      () =>
        createEntity(
          projectId,
          {
            kind: 'asset',
            ui_kind: 'asset',
            resource_id: 'asset:bad',
            state: { file_reference: 'x' },
          },
          adminId,
        ),
      (error: unknown) =>
        error instanceof ApiError && error.code === 'VALIDATION',
    )
  })

  it('file-tree / progress-dag 容器持有拓扑，节点不携带拓扑', () => {
    const tree = createEntity(
      projectId,
      {
        kind: 'file-tree',
        ui_kind: 'file-tree',
        resource_id: 'file-tree:main',
        state: {
          rootId: 'root',
          nodes: {
            root: { id: 'root', name: '/', isDirectory: true, inode: null, parent: null, order: 0 },
          },
        },
      },
      adminId,
    )
    createEntity(
      projectId,
      {
        kind: 'file-node',
        ui_kind: 'form',
        resource_id: 'inode:dir',
        state: {
          stable_id: 'dir',
          display: {},
          hidden: false,
        },
      },
      adminId,
    )
    assert.throws(
      () =>
        createEntity(
          projectId,
          {
            kind: 'file-node',
            ui_kind: 'form',
            resource_id: 'inode:bad',
            state: {
              stable_id: 'bad',
              display: {},
              hidden: false,
              parent_stable_id: 'dir',
            },
          },
          adminId,
        ),
      (error: unknown) =>
        error instanceof ApiError && error.code === 'VALIDATION',
    )

    const dag = createEntity(
      projectId,
      {
        kind: 'progress-dag',
        ui_kind: 'progress-dag',
        resource_id: 'progress-dag:main',
        state: {
          entry_stable_ids: ['start'],
          successors: { start: ['end'] },
        },
      },
      adminId,
    )
    assert.deepEqual(dag.state.successors, { start: ['end'] })
    assert.throws(
      () =>
        createEntity(
          projectId,
          {
            kind: 'progress-node',
            ui_kind: 'dag-node',
            resource_id: 'pnode:start',
            state: {
              triggers_checkpoint: false,
              successors: ['end'],
            },
          },
          adminId,
        ),
      (error: unknown) =>
        error instanceof ApiError && error.code === 'VALIDATION',
    )

    // 整容器 patch：nodes / successors
    const updatedTree = patchEntity(
      projectId,
      tree.id,
      `${tree.id}@state:/nodes`,
      {
        root: { id: 'root', name: '/', isDirectory: true, inode: null, parent: null, order: 0 },
        dir: { id: 'dir', name: 'dir', isDirectory: true, inode: null, parent: 'root', order: 0 },
      },
      adminId,
    )
    assert.deepEqual(updatedTree.state.nodes.dir, {
      id: 'dir',
      name: 'dir',
      isDirectory: true,
      inode: null,
      parent: 'root',
      order: 0,
    })
  })

  it('不存在实体抛 ENTITY_NOT_FOUND', () => {
    assert.throws(
      () => requireEntity(projectId, 'missing'),
      (error: unknown) =>
        error instanceof ApiError && error.code === 'ENTITY_NOT_FOUND',
    )
  })
})
