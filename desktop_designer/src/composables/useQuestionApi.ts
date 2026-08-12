/**
 * # useQuestionApi — 题目数据访问层（远程后端优先，localStorage 回退）
 *
 * 所有题目操作的统一入口（CRUD / 审核 / 发布导出 / 权限校验）。
 * 模式由 config/api.ts 的 USE_REMOTE_API 控制：
 * - 远程：调用 server/ 的 /api/v1/questions/*，token 取自登录会话
 * - 本地：localStorage 模拟（旧行为回退）
 *
 * 全部函数为 async，未来接口形状与本文件签名保持一致。
 *
 * ## 权限规则（服务端与本地一致）
 *
 * - author：仅本人题目可见/编辑/删除/提交审核/测试
 * - admin：全部可见、任意删除、审核（通过/驳回）
 * - 已发布（approved）题目被编辑后自动重置为 pending（需重新审核）
 */

import { QUESTION_API_BASE, USE_REMOTE_API } from '@/config/api'
import type { ContentBlock, PuzzleDefinition, PuzzleOption, QuestionType, WrongFeedback } from '@/types/puzzle'

/** 题目状态：草稿 / 待审核 / 已发布 / 已驳回 */
export type QuestionStatus = 'draft' | 'pending' | 'approved' | 'rejected'

/** 题目记录（含管理字段） */
export interface QuestionRecord {
  id: string
  authorUsername: string
  title: string
  blocks: ContentBlock[]
  type: QuestionType
  options?: PuzzleOption[]
  fillAnswers?: string[]
  hints?: string[]
  explanation?: string
  /** 错误反馈规则（答错提示，可选） */
  wrongFeedback?: WrongFeedback
  status: QuestionStatus
  /** 审核备注（驳回原因等） */
  reviewNote?: string
  createdAt: string
  updatedAt: string
  publishedAt?: string
}

/** 当前操作者视图（来自 auth store） */
export interface AuthorView {
  username: string
  role: 'author' | 'admin'
}

/** 题目编辑输入（不含管理字段） */
export type QuestionInput = Omit<
  QuestionRecord,
  'id' | 'authorUsername' | 'status' | 'reviewNote' | 'createdAt' | 'updatedAt' | 'publishedAt'
>

// ─── 远程模式工具 ───────────────────────────────────

/** 从登录会话读取 token */
function getToken(): string | null {
  try {
    const session = JSON.parse(localStorage.getItem('ellia.question.session') ?? 'null') as
      | { token?: string }
      | null
    return session?.token ?? null
  } catch {
    return null
  }
}

/** 远程请求：自动带 Bearer token，非 2xx 抛出 { status, error } */
async function remoteFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken()
  const response = await fetch(`${QUESTION_API_BASE}/api/v1/questions${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  })
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const data = await response.json()
      if (data?.error) message = data.error
    } catch {
      // 忽略非 JSON 响应体
    }
    throw Object.assign(new Error(message), { status: response.status })
  }
  return response
}

// ─── 本地模拟模式（旧行为回退） ─────────────────────

const QUESTIONS_KEY = 'ellia.question.questions'

function readAll(): QuestionRecord[] {
  try {
    return JSON.parse(localStorage.getItem(QUESTIONS_KEY) ?? '[]') as QuestionRecord[]
  } catch {
    return []
  }
}

function writeAll(questions: QuestionRecord[]): void {
  localStorage.setItem(QUESTIONS_KEY, JSON.stringify(questions))
}

function createLocalId(): string {
  return `q-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

function canManageLocal(viewer: AuthorView, question: QuestionRecord): boolean {
  return viewer.role === 'admin' || question.authorUsername === viewer.username
}

// ─── 对外 API（远程 / 本地双分支） ───────────────────

/**
 * 列出当前操作者可见的题目（author 本人 / admin 全部）。
 *
 * @param viewer - 操作者
 * @returns 题目列表（按更新时间倒序）
 */
export async function listQuestions(viewer: AuthorView): Promise<QuestionRecord[]> {
  if (USE_REMOTE_API) {
    const path = viewer.role === 'admin' ? '/all' : '/mine'
    const response = await remoteFetch(path)
    return (await response.json()) as QuestionRecord[]
  }
  const all = readAll().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
  return viewer.role === 'admin' ? all : all.filter((q) => q.authorUsername === viewer.username)
}

/**
 * 列出所有已发布题目（所有登录用户可见，只读；admin 可打回/删除）。
 *
 * @returns 已发布题目列表（按发布时间正序）
 */
export async function listPublishedQuestions(): Promise<QuestionRecord[]> {
  if (USE_REMOTE_API) {
    const response = await remoteFetch('/published')
    const data = (await response.json()) as { version: number; questions: QuestionRecord[] }
    return data.questions
  }
  return readAll()
    .filter((question) => question.status === 'approved')
    .sort((a, b) => (a.publishedAt ?? '').localeCompare(b.publishedAt ?? ''))
}

/**
 * 打回已发布题目（admin）：approved → draft（下架，作者可重新编辑后再提交审核）。
 *
 * @param viewer - 操作者（须 admin）
 * @param id     - 题目 id
 * @returns 结果
 */
export async function unpublishQuestion(
  viewer: AuthorView,
  id: string,
): Promise<{ ok: boolean; error?: string }> {
  if (USE_REMOTE_API) {
    try {
      await remoteFetch(`/${id}/unpublish`, { method: 'POST', body: '{}' })
      return { ok: true }
    } catch (error) {
      return { ok: false, error: (error as Error).message }
    }
  }
  if (viewer.role !== 'admin') return { ok: false, error: '仅管理员可打回' }
  const all = readAll()
  const index = all.findIndex((question) => question.id === id)
  if (index === -1) return { ok: false, error: '题目不存在' }
  if (all[index].status !== 'approved') return { ok: false, error: '仅已发布的题目可打回' }
  all[index] = {
    ...all[index],
    status: 'draft',
    reviewNote: undefined,
    publishedAt: undefined,
    updatedAt: new Date().toISOString(),
  }
  writeAll(all)
  return { ok: true }
}

/**
 * 按 id 取题目。
 *
 * @param id - 题目 id
 * @returns 题目记录或 null（未找到）
 */
export async function getQuestion(id: string): Promise<QuestionRecord | null> {
  if (USE_REMOTE_API) {
    try {
      const response = await remoteFetch(`/${id}`)
      return (await response.json()) as QuestionRecord
    } catch (error) {
      if ((error as { status?: number }).status === 404) return null
      throw error
    }
  }
  return readAll().find((question) => question.id === id) ?? null
}

/**
 * 创建题目（草稿）。
 *
 * @param _authorUsername - 作者（远程模式由服务端从 token 识别，忽略此参数）
 * @param input           - 题目内容
 * @returns 新题目记录
 */
export async function createQuestion(_authorUsername: string, input: QuestionInput): Promise<QuestionRecord> {
  if (USE_REMOTE_API) {
    const response = await remoteFetch('/', { method: 'POST', body: JSON.stringify(input) })
    return (await response.json()) as QuestionRecord
  }
  const now = new Date().toISOString()
  const question: QuestionRecord = {
    id: createLocalId(),
    authorUsername: _authorUsername,
    status: 'draft',
    createdAt: now,
    updatedAt: now,
    ...input,
  }
  const all = readAll()
  all.push(question)
  writeAll(all)
  return question
}

/**
 * 编辑题目（本人或 admin）。已发布题编辑后自动重置为 pending。
 *
 * @param viewer - 操作者
 * @param id     - 题目 id
 * @param patch  - 更新的字段
 * @returns 结果
 */
export async function updateQuestion(
  viewer: AuthorView,
  id: string,
  patch: Partial<QuestionInput>,
): Promise<{ ok: boolean; error?: string }> {
  if (USE_REMOTE_API) {
    try {
      await remoteFetch(`/${id}`, { method: 'PUT', body: JSON.stringify(patch) })
      return { ok: true }
    } catch (error) {
      return { ok: false, error: (error as Error).message }
    }
  }
  const all = readAll()
  const index = all.findIndex((question) => question.id === id)
  if (index === -1) return { ok: false, error: '题目不存在' }
  const question = all[index]
  if (!canManageLocal(viewer, question)) return { ok: false, error: '无权编辑他人题目' }

  const wasApproved = question.status === 'approved'
  all[index] = {
    ...question,
    ...patch,
    status: wasApproved ? 'pending' : question.status,
    reviewNote: wasApproved ? undefined : question.reviewNote,
    publishedAt: wasApproved ? undefined : question.publishedAt,
    updatedAt: new Date().toISOString(),
  }
  writeAll(all)
  return { ok: true }
}

/**
 * 删除题目（本人或 admin 任意）。
 *
 * @param viewer - 操作者
 * @param id     - 题目 id
 * @returns 是否删除成功
 */
export async function deleteQuestion(viewer: AuthorView, id: string): Promise<boolean> {
  if (USE_REMOTE_API) {
    try {
      await remoteFetch(`/${id}`, { method: 'DELETE' })
      return true
    } catch {
      return false
    }
  }
  const all = readAll()
  const question = all.find((candidate) => candidate.id === id)
  if (!question || !canManageLocal(viewer, question)) return false
  writeAll(all.filter((candidate) => candidate.id !== id))
  return true
}

/**
 * 提交审核（本人）：draft / rejected → pending。
 *
 * @param viewer - 操作者
 * @param id     - 题目 id
 * @returns 结果
 */
export async function submitForReview(
  viewer: AuthorView,
  id: string,
): Promise<{ ok: boolean; error?: string }> {
  if (USE_REMOTE_API) {
    try {
      await remoteFetch(`/${id}/submit`, { method: 'POST', body: '{}' })
      return { ok: true }
    } catch (error) {
      return { ok: false, error: (error as Error).message }
    }
  }
  const all = readAll()
  const index = all.findIndex((question) => question.id === id)
  if (index === -1) return { ok: false, error: '题目不存在' }
  const question = all[index]
  if (!canManageLocal(viewer, question)) return { ok: false, error: '无权操作他人题目' }
  if (question.status === 'approved') return { ok: false, error: '已发布的题目无需再次提交' }

  all[index] = { ...question, status: 'pending', updatedAt: new Date().toISOString() }
  writeAll(all)
  return { ok: true }
}

/**
 * 管理员审核：approve → approved（写入 publishedAt）；reject → rejected（附备注）。
 *
 * @param viewer   - 操作者（须 admin）
 * @param id       - 题目 id
 * @param approved - 是否通过
 * @param note     - 审核备注
 * @returns 结果
 */
export async function reviewQuestion(
  viewer: AuthorView,
  id: string,
  approved: boolean,
  note?: string,
): Promise<{ ok: boolean; error?: string }> {
  if (USE_REMOTE_API) {
    try {
      await remoteFetch(`/${id}/review`, {
        method: 'POST',
        body: JSON.stringify({ approved, note }),
      })
      return { ok: true }
    } catch (error) {
      return { ok: false, error: (error as Error).message }
    }
  }
  if (viewer.role !== 'admin') return { ok: false, error: '仅管理员可审核' }
  const all = readAll()
  const index = all.findIndex((question) => question.id === id)
  if (index === -1) return { ok: false, error: '题目不存在' }

  const now = new Date().toISOString()
  all[index] = {
    ...all[index],
    status: approved ? 'approved' : 'rejected',
    reviewNote: note?.trim() || undefined,
    publishedAt: approved ? now : undefined,
    updatedAt: now,
  }
  writeAll(all)
  return { ok: true }
}

/**
 * 导出已发布题库（供游戏端自动发现）。
 *
 * @returns 发布文件内容 { version, questions }
 */
export async function exportPublishedQuestions(): Promise<{ version: number; questions: PuzzleDefinition[] }> {
  if (USE_REMOTE_API) {
    const response = await fetch(`${QUESTION_API_BASE}/api/v1/questions/published`)
    if (!response.ok) throw new Error('拉取已发布题库失败')
    return (await response.json()) as { version: number; questions: PuzzleDefinition[] }
  }
  const questions: PuzzleDefinition[] = readAll()
    .filter((question) => question.status === 'approved')
    .sort((a, b) => (a.publishedAt ?? '').localeCompare(b.publishedAt ?? ''))
    .map((question) => ({
      id: question.id,
      title: question.title,
      blocks: question.blocks,
      type: question.type,
      options: question.options,
      fillAnswers: question.fillAnswers,
      hints: question.hints,
      explanation: question.explanation,
      wrongFeedback: question.wrongFeedback,
    }))
  return { version: 1, questions }
}
