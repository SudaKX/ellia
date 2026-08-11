/**
 * # useQuestionApi — 题目数据访问层
 *
 * 出题器所有题目操作的统一入口（CRUD / 审核 / 发布导出 / 权限校验）。
 * 当前为 localStorage 实现；未来切后端时只需改写本文件内部实现，
 * 对外函数签名保持不变（对应计划 B 节"切换点"）。
 *
 * ## 权限规则
 *
 * - author：仅本人题目可见/编辑/删除/提交审核
 * - admin：全部可见、任意删除、审核（通过/驳回）
 * - 已发布（approved）题目被编辑后自动重置为 pending（需重新审核）
 */

import type { ContentBlock, PuzzleDefinition, PuzzleOption, QuestionType } from '@/types/puzzle'

/** 题目状态：草稿 / 待审核 / 已发布 / 已驳回 */
export type QuestionStatus = 'draft' | 'pending' | 'approved' | 'rejected'

/** 题目记录（含管理字段，仅存于出题器本地） */
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

function createId(): string {
  return `q-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

/** 本人 or 管理员？ */
function canManage(viewer: AuthorView, question: QuestionRecord): boolean {
  return viewer.role === 'admin' || question.authorUsername === viewer.username
}

/** 题目编辑输入（不含管理字段） */
export type QuestionInput = Omit<
  QuestionRecord,
  'id' | 'authorUsername' | 'status' | 'reviewNote' | 'createdAt' | 'updatedAt' | 'publishedAt'
>

/**
 * 列出当前操作者可见的题目（按更新时间倒序）。
 *
 * @param viewer - 操作者
 * @returns 题目列表（author 仅本人；admin 全部）
 */
export function listQuestions(viewer: AuthorView): QuestionRecord[] {
  const all = readAll().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
  return viewer.role === 'admin' ? all : all.filter((q) => q.authorUsername === viewer.username)
}

/**
 * 按 id 取题目。
 *
 * @param id - 题目 id
 * @returns 题目记录或 null
 */
export function getQuestion(id: string): QuestionRecord | null {
  return readAll().find((question) => question.id === id) ?? null
}

/**
 * 创建题目（草稿）。
 *
 * @param authorUsername - 作者用户名
 * @param input          - 题目内容
 * @returns 新题目记录
 */
export function createQuestion(authorUsername: string, input: QuestionInput): QuestionRecord {
  const now = new Date().toISOString()
  const question: QuestionRecord = {
    id: createId(),
    authorUsername,
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
 * 编辑题目（本人或 admin）。
 * 已发布题被编辑后重置为 pending（需重新审核）。
 *
 * @param viewer - 操作者
 * @param id     - 题目 id
 * @param patch  - 更新的字段
 * @returns 结果
 */
export function updateQuestion(
  viewer: AuthorView,
  id: string,
  patch: Partial<QuestionInput>,
): { ok: boolean; error?: string } {
  const all = readAll()
  const index = all.findIndex((question) => question.id === id)
  if (index === -1) return { ok: false, error: '题目不存在' }
  const question = all[index]
  if (!canManage(viewer, question)) return { ok: false, error: '无权编辑他人题目' }

  const wasApproved = question.status === 'approved'
  all[index] = {
    ...question,
    ...patch,
    // 编辑已发布题 → 重置为待审核
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
export function deleteQuestion(viewer: AuthorView, id: string): boolean {
  const all = readAll()
  const question = all.find((candidate) => candidate.id === id)
  if (!question || !canManage(viewer, question)) return false
  writeAll(all.filter((candidate) => candidate.id !== id))
  return true
}

/**
 * 提交审核（本人）：draft / rejected → pending。
 * 已发布题不可重复提交。
 *
 * @param viewer - 操作者
 * @param id     - 题目 id
 * @returns 结果
 */
export function submitForReview(viewer: AuthorView, id: string): { ok: boolean; error?: string } {
  const all = readAll()
  const index = all.findIndex((question) => question.id === id)
  if (index === -1) return { ok: false, error: '题目不存在' }
  const question = all[index]
  if (!canManage(viewer, question)) return { ok: false, error: '无权操作他人题目' }
  if (question.status === 'approved') return { ok: false, error: '已发布的题目无需再次提交' }

  all[index] = { ...question, status: 'pending', updatedAt: new Date().toISOString() }
  writeAll(all)
  return { ok: true }
}

/**
 * 管理员审核：approve → approved（记录 publishedAt）；reject → rejected（附备注）。
 *
 * @param viewer  - 操作者（须 admin）
 * @param id      - 题目 id
 * @param approved- 是否通过
 * @param note    - 审核备注（驳回原因等）
 * @returns 结果
 */
export function reviewQuestion(
  viewer: AuthorView,
  id: string,
  approved: boolean,
  note?: string,
): { ok: boolean; error?: string } {
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
 * 导出已发布题库（供 desktop 自动发现）。
 * 剔除管理字段（作者/审核备注/时间），保留完整 definition（含答案，供游戏本地校验）。
 *
 * @returns 发布文件内容 { version, questions }
 */
export function exportPublishedQuestions(): { version: number; questions: PuzzleDefinition[] } {
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
    }))
  return { version: 1, questions }
}
