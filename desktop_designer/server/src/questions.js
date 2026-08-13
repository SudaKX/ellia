/**
 * 题目路由：CRUD + 状态机 + 审核 + 发布 + 测试。
 *
 * 权限矩阵：
 * - author：仅本人题目（创建/读取/编辑/删除/提交审核/测试）
 * - admin：全部题目可见、任意删除、审核（通过/驳回）
 * - published：公开只读，无需登录
 *
 * 生命周期：draft → pending → approved | rejected；编辑已发布题自动回到 pending。
 */

import { Router } from 'express'

import { db } from './db.js'
import { requireAdmin, requireAuth } from './auth.js'

export const questionsRouter = Router()

// ─── 校验与序列化 ───────────────────────────────────

const TYPES = new Set(['single', 'multi', 'fill'])

/** 校验题目输入，返回错误信息（null 表示通过） */
function validateQuestionInput(input) {
  if (!input || typeof input !== 'object') return '请求体格式错误'
  if (!String(input.title ?? '').trim()) return '请填写题目标题'
  if (!Array.isArray(input.blocks) || input.blocks.length === 0) return '请至少填写一段题面内容'
  if (!TYPES.has(input.type)) return '题型不合法'

  if (input.type === 'single' || input.type === 'multi') {
    const options = Array.isArray(input.options) ? input.options : []
    if (options.length < 2 || options.length > 10) return '选择题选项数量需在 2~10 之间'
    if (options.some((option) => !String(option?.text ?? '').trim())) return '选项文本不能为空'
    if (!options.some((option) => option?.correct === true)) return '请标记至少一个正确答案'
  }
  if (input.type === 'fill') {
    const answers = Array.isArray(input.fillAnswers) ? input.fillAnswers : []
    if (answers.length < 1) return '填空至少一个空'
    if (answers.some((answer) => !String(answer ?? '').trim())) return '填空答案不能为空'
  }

  // 错误反馈规则（可选）：结构校验
  const feedback = input.wrongFeedback
  if (feedback !== undefined && feedback !== null) {
    if (typeof feedback !== 'object' || Array.isArray(feedback)) return '错误反馈规则格式错误'
    if (feedback.optionHints !== undefined && (typeof feedback.optionHints !== 'object' || Array.isArray(feedback.optionHints))) {
      return '选项错误提示格式错误'
    }
    for (const [key, value] of Object.entries(feedback.optionHints ?? {})) {
      if (!/^\d+$/.test(key) || typeof value !== 'string') return '选项错误提示格式错误'
    }
    if (feedback.fillHints !== undefined && (!Array.isArray(feedback.fillHints) || feedback.fillHints.some((hint) => typeof hint !== 'string'))) {
      return '填空错误提示格式错误'
    }
    if (feedback.attemptHints !== undefined && (!Array.isArray(feedback.attemptHints) || feedback.attemptHints.some((hint) => typeof hint !== 'string'))) {
      return '次数错误提示格式错误'
    }
  }
  return null
}

/** 数据库行 → API 记录（补上 authorUsername，剔除 password 等） */
function rowToQuestion(row) {
  return {
    id: row.id,
    authorUsername: row.author_username,
    title: row.title,
    blocks: JSON.parse(row.blocks ?? '[]'),
    type: row.type,
    options: row.options ? JSON.parse(row.options) : undefined,
    fillAnswers: row.fill_answers ? JSON.parse(row.fill_answers) : undefined,
    hints: row.hints ? JSON.parse(row.hints) : undefined,
    explanation: row.explanation ?? undefined,
    wrongFeedback: row.wrong_feedback ? JSON.parse(row.wrong_feedback) : undefined,
    status: row.status,
    reviewNote: row.review_note ?? undefined,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    publishedAt: row.published_at ?? undefined,
  }
}

/** 题目 → 发布用的 PuzzleDefinition（剔除管理字段，含答案供游戏本地校验） */
function questionToPublished(row) {
  return {
    id: row.id,
    title: row.title,
    blocks: JSON.parse(row.blocks ?? '[]'),
    type: row.type,
    options: row.options ? JSON.parse(row.options) : undefined,
    fillAnswers: row.fill_answers ? JSON.parse(row.fill_answers) : undefined,
    hints: row.hints ? JSON.parse(row.hints) : undefined,
    explanation: row.explanation ?? undefined,
    wrongFeedback: row.wrong_feedback ? JSON.parse(row.wrong_feedback) : undefined,
    // 附加管理字段：供出题器端「已发布题库」展示作者 / 打回 / 删除（游戏端忽略多余字段）
    authorUsername: row.author_username,
    status: row.status,
    publishedAt: row.published_at ?? undefined,
  }
}

/** 统一查询列（含作者名，供列表/详情直接返回） */
const SELECT_COLUMNS = `
  q.id, q.author_id, q.title, q.blocks, q.type, q.options, q.fill_answers,
  q.hints, q.explanation, q.wrong_feedback, q.status, q.review_note,
  q.created_at, q.updated_at, q.published_at,
  u.username AS author_username
`

// ─── 题目创建 / 读取 ────────────────────────────────

/** POST /api/v1/questions — 创建草稿（author） */
questionsRouter.post('/', requireAuth, (req, res, next) => {
  try {
    const validation = validateQuestionInput(req.body)
    if (validation) return res.status(422).json({ error: validation })

    const body = req.body
    const now = new Date().toISOString()
    const id = crypto.randomUUID()
    db.prepare(
      `INSERT INTO questions
       (id, author_id, title, blocks, type, options, fill_answers, hints, explanation,
        wrong_feedback, status, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)`,
    ).run(
      id,
      req.user.sub,
      String(body.title).trim(),
      JSON.stringify(body.blocks),
      body.type,
      body.options ? JSON.stringify(body.options) : null,
      body.fillAnswers ? JSON.stringify(body.fillAnswers) : null,
      body.hints ? JSON.stringify(body.hints) : null,
      body.explanation ? String(body.explanation).trim() : null,
      body.wrongFeedback ? JSON.stringify(body.wrongFeedback) : null,
      now,
      now,
    )
    const row = db.prepare(`SELECT ${SELECT_COLUMNS} FROM questions q JOIN users u ON u.id = q.author_id WHERE q.id = ?`).get(id)
    return res.status(201).json(rowToQuestion(row))
  } catch (error) {
    return next(error)
  }
})

/** GET /api/v1/questions/mine — 我的题目（author） */
questionsRouter.get('/mine', requireAuth, (req, res, next) => {
  try {
    const rows = db
      .prepare(`SELECT ${SELECT_COLUMNS} FROM questions q JOIN users u ON u.id = q.author_id WHERE q.author_id = ? ORDER BY q.updated_at DESC`)
      .all(req.user.sub)
    return res.json(rows.map(rowToQuestion))
  } catch (error) {
    return next(error)
  }
})

/** GET /api/v1/questions/all — 全部题目（admin） */
questionsRouter.get('/all', requireAuth, requireAdmin, (_req, res, next) => {
  try {
    const rows = db
      .prepare(`SELECT ${SELECT_COLUMNS} FROM questions q JOIN users u ON u.id = q.author_id ORDER BY q.updated_at DESC`)
      .all()
    return res.json(rows.map(rowToQuestion))
  } catch (error) {
    return next(error)
  }
})

/** GET /api/v1/questions/published — 已发布题目（公开只读，匿名可访问） */
questionsRouter.get('/published', (_req, res, next) => {
  try {
    const rows = db
      .prepare(`SELECT ${SELECT_COLUMNS} FROM questions q JOIN users u ON u.id = q.author_id WHERE q.status = 'approved' ORDER BY q.published_at ASC`)
      .all()
    return res.json({ version: 1, questions: rows.map(questionToPublished) })
  } catch (error) {
    return next(error)
  }
})

/** GET /api/v1/questions/:id — 单题（本人或 admin） */
questionsRouter.get('/:id', requireAuth, (req, res, next) => {
  try {
    const row = db.prepare(`SELECT ${SELECT_COLUMNS} FROM questions q JOIN users u ON u.id = q.author_id WHERE q.id = ?`).get(req.params.id)
    if (!row) return res.status(404).json({ error: '题目不存在' })
    if (row.author_id !== req.user.sub && req.user.role !== 'admin') {
      return res.status(403).json({ error: '无权查看他人题目' })
    }
    return res.json(rowToQuestion(row))
  } catch (error) {
    return next(error)
  }
})

// ─── 编辑 / 删除 ────────────────────────────────────

/** PUT /api/v1/questions/:id — 编辑（本人；approved 编辑后回到 pending） */
questionsRouter.put('/:id', requireAuth, (req, res, next) => {
  try {
    const validation = validateQuestionInput(req.body)
    if (validation) return res.status(422).json({ error: validation })

    const row = db.prepare('SELECT * FROM questions WHERE id = ?').get(req.params.id)
    if (!row) return res.status(404).json({ error: '题目不存在' })
    if (row.author_id !== req.user.sub && req.user.role !== 'admin') {
      return res.status(403).json({ error: '无权编辑他人题目' })
    }

    const body = req.body
    const wasApproved = row.status === 'approved'
    const now = new Date().toISOString()
    db.prepare(
      `UPDATE questions SET
         title = ?, blocks = ?, type = ?, options = ?, fill_answers = ?, hints = ?, explanation = ?,
         wrong_feedback = ?, status = ?, review_note = ?, published_at = ?, updated_at = ?
       WHERE id = ?`,
    ).run(
      String(body.title).trim(),
      JSON.stringify(body.blocks),
      body.type,
      body.options ? JSON.stringify(body.options) : null,
      body.fillAnswers ? JSON.stringify(body.fillAnswers) : null,
      body.hints ? JSON.stringify(body.hints) : null,
      body.explanation ? String(body.explanation).trim() : null,
      body.wrongFeedback ? JSON.stringify(body.wrongFeedback) : null,
      wasApproved ? 'pending' : row.status,
      wasApproved ? null : row.review_note,
      wasApproved ? null : row.published_at,
      now,
      row.id,
    )
    const updated = db.prepare(`SELECT ${SELECT_COLUMNS} FROM questions q JOIN users u ON u.id = q.author_id WHERE q.id = ?`).get(row.id)
    return res.json(rowToQuestion(updated))
  } catch (error) {
    return next(error)
  }
})

/** DELETE /api/v1/questions/:id — 删除（本人；admin 任意） */
questionsRouter.delete('/:id', requireAuth, (req, res, next) => {
  try {
    const row = db.prepare('SELECT * FROM questions WHERE id = ?').get(req.params.id)
    if (!row) return res.status(404).json({ error: '题目不存在' })
    if (row.author_id !== req.user.sub && req.user.role !== 'admin') {
      return res.status(403).json({ error: '无权删除他人题目' })
    }
    db.prepare('DELETE FROM questions WHERE id = ?').run(req.params.id)
    return res.status(204).end()
  } catch (error) {
    return next(error)
  }
})

// ─── 状态机：提交审核 / 审核 ────────────────────────

/** POST /api/v1/questions/:id/submit — 提交审核（本人；draft/rejected → pending） */
questionsRouter.post('/:id/submit', requireAuth, (req, res, next) => {
  try {
    const row = db.prepare('SELECT * FROM questions WHERE id = ?').get(req.params.id)
    if (!row) return res.status(404).json({ error: '题目不存在' })
    if (row.author_id !== req.user.sub && req.user.role !== 'admin') {
      return res.status(403).json({ error: '无权操作他人题目' })
    }
    if (row.status === 'approved') return res.status(409).json({ error: '已发布的题目无需再次提交' })

    db.prepare("UPDATE questions SET status = 'pending', updated_at = ? WHERE id = ?").run(
      new Date().toISOString(),
      row.id,
    )
    const updated = db.prepare(`SELECT ${SELECT_COLUMNS} FROM questions q JOIN users u ON u.id = q.author_id WHERE q.id = ?`).get(row.id)
    return res.json(rowToQuestion(updated))
  } catch (error) {
    return next(error)
  }
})

/** POST /api/v1/questions/:id/review — 审核（admin；pending → approved/rejected） */
questionsRouter.post('/:id/review', requireAuth, requireAdmin, (req, res, next) => {
  try {
    const row = db.prepare('SELECT * FROM questions WHERE id = ?').get(req.params.id)
    if (!row) return res.status(404).json({ error: '题目不存在' })
    if (row.status !== 'pending') return res.status(409).json({ error: '仅待审核状态的题目可审核' })

    const approved = req.body?.approved === true
    const note = req.body?.note ? String(req.body.note).trim() : null
    const now = new Date().toISOString()
    db.prepare(
      "UPDATE questions SET status = ?, review_note = ?, published_at = ?, updated_at = ? WHERE id = ?",
    ).run(approved ? 'approved' : 'rejected', note, approved ? now : null, now, row.id)
    const updated = db.prepare(`SELECT ${SELECT_COLUMNS} FROM questions q JOIN users u ON u.id = q.author_id WHERE q.id = ?`).get(row.id)
    return res.json(rowToQuestion(updated))
  } catch (error) {
    return next(error)
  }
})

/** POST /api/v1/questions/:id/unpublish — 打回（admin；approved → draft，下架） */
questionsRouter.post('/:id/unpublish', requireAuth, requireAdmin, (req, res, next) => {
  try {
    const row = db.prepare('SELECT * FROM questions WHERE id = ?').get(req.params.id)
    if (!row) return res.status(404).json({ error: '题目不存在' })
    if (row.status !== 'approved') return res.status(409).json({ error: '仅已发布的题目可打回' })

    const now = new Date().toISOString()
    db.prepare(
      "UPDATE questions SET status = 'draft', review_note = NULL, published_at = NULL, updated_at = ? WHERE id = ?",
    ).run(now, row.id)
    const updated = db.prepare(`SELECT ${SELECT_COLUMNS} FROM questions q JOIN users u ON u.id = q.author_id WHERE q.id = ?`).get(row.id)
    return res.json(rowToQuestion(updated))
  } catch (error) {
    return next(error)
  }
})

// ─── 测试（答案校验，不落库） ───────────────────────

/** 校验答案：单选/多选（选项下标集合）/填空（值列表） */
function checkAnswer(row, selectedIndices, fillValues) {
  const type = row.type
  if (type === 'single' || type === 'multi') {
    const options = JSON.parse(row.options ?? '[]')
    const selected = Array.isArray(selectedIndices) ? selectedIndices.map(Number) : []
    if (type === 'single') {
      if (selected.length !== 1) return false
      return options[selected[0]]?.correct === true
    }
    const correct = options.map((option, index) => (option.correct ? index : -1)).filter((i) => i !== -1)
    const a = [...selected].sort((x, y) => x - y)
    const b = [...correct].sort((x, y) => x - y)
    if (a.length !== b.length) return false
    return a.every((value, i) => value === b[i])
  }
  if (type === 'fill') {
    const answers = JSON.parse(row.fill_answers ?? '[]')
    if (!Array.isArray(fillValues) || fillValues.length !== answers.length) return false
    const norm = (value) => String(value).trim().toLowerCase()
    return fillValues.every((value, i) => norm(value) === norm(answers[i]))
  }
  return false
}

/** POST /api/v1/questions/:id/test — 测试答案（本人；不落库） */
questionsRouter.post('/:id/test', requireAuth, (req, res, next) => {
  try {
    const row = db.prepare('SELECT * FROM questions WHERE id = ?').get(req.params.id)
    if (!row) return res.status(404).json({ error: '题目不存在' })
    if (row.author_id !== req.user.sub && req.user.role !== 'admin') {
      return res.status(403).json({ error: '无权测试他人题目' })
    }
    const accepted = checkAnswer(row, req.body?.selectedIndices, req.body?.fillValues)
    return res.json({ accepted })
  } catch (error) {
    return next(error)
  }
})
