/**
 * # useQuestionsStore — 题目列表状态（Pinia 响应式包装）
 *
 * 持有当前操作者可见的题目列表，方法内部委托 useQuestionApi（数据访问层），
 * 操作成功后刷新列表。权限判断在 useQuestionApi 内统一处理（远程 / 本地）。
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import {
  createQuestion,
  deleteQuestion,
  exportPublishedQuestions,
  listPublishedQuestions,
  listQuestions,
  reviewQuestion,
  submitForReview,
  unpublishQuestion,
  updateQuestion,
  type QuestionInput,
  type QuestionRecord,
} from '@/composables/useQuestionApi'

export const useQuestionsStore = defineStore('questions', () => {
  /** 当前可见题目列表（本人 / admin 全部） */
  const questions = ref<QuestionRecord[]>([])
  /** 已发布题目列表（所有登录用户可见） */
  const published = ref<QuestionRecord[]>([])

  /** 当前操作者（auth store） */
  function viewer() {
    const auth = useAuthStore()
    const user = auth.currentUser
    if (!user) return null
    return { username: user.username, role: user.role }
  }

  /** 加载列表（登录后 / 操作后调用） */
  async function load(): Promise<void> {
    const current = viewer()
    if (!current) return
    try {
      questions.value = await listQuestions(current)
    } catch (error) {
      questions.value = []
      throw error
    }
  }

  /** 加载已发布题库（登录后 / 打回 / 删除后调用） */
  async function loadPublished(): Promise<void> {
    try {
      published.value = await listPublishedQuestions()
    } catch (error) {
      published.value = []
      throw error
    }
  }

  /** 创建题目（草稿） */
  async function create(input: QuestionInput): Promise<QuestionRecord | null> {
    const current = viewer()
    if (!current) return null
    const record = await createQuestion(current.username, input)
    await load()
    return record
  }

  /** 编辑题目 */
  async function update(id: string, patch: Partial<QuestionInput>): Promise<{ ok: boolean; error?: string }> {
    const current = viewer()
    if (!current) return { ok: false, error: '未登录' }
    const result = await updateQuestion(current, id, patch)
    await load()
    return result
  }

  /** 删除题目 */
  async function remove(id: string): Promise<boolean> {
    const current = viewer()
    if (!current) return false
    const ok = await deleteQuestion(current, id)
    await load()
    await loadPublished().catch(() => undefined)
    return ok
  }

  /** 打回已发布题目（admin）：approved → draft */
  async function unpublish(id: string): Promise<{ ok: boolean; error?: string }> {
    const current = viewer()
    if (!current) return { ok: false, error: '未登录' }
    const result = await unpublishQuestion(current, id)
    await load()
    await loadPublished().catch(() => undefined)
    return result
  }

  /** 提交审核 */
  async function submit(id: string): Promise<{ ok: boolean; error?: string }> {
    const current = viewer()
    if (!current) return { ok: false, error: '未登录' }
    const result = await submitForReview(current, id)
    await load()
    return result
  }

  /** 管理员审核 */
  async function review(id: string, approved: boolean, note?: string): Promise<{ ok: boolean; error?: string }> {
    const current = viewer()
    if (!current) return { ok: false, error: '未登录' }
    const result = await reviewQuestion(current, id, approved, note)
    await load()
    return result
  }

  /** 导出已发布题库（下载 / 复制） */
  async function exportPublished() {
    return exportPublishedQuestions()
  }

  return { questions, published, load, loadPublished, create, update, remove, unpublish, submit, review, exportPublished }
})
