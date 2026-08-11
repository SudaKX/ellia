/**
 * # useQuestionsStore — 题目列表状态（Pinia 响应式包装）
 *
 * 持有当前操作者可见的题目列表，方法内部委托 useQuestionApi（数据访问层），
 * 操作成功后刷新列表。权限判断在 useQuestionApi 内统一处理。
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import {
  createQuestion,
  deleteQuestion,
  exportPublishedQuestions,
  listQuestions,
  reviewQuestion,
  submitForReview,
  updateQuestion,
  type QuestionInput,
  type QuestionRecord,
} from '@/composables/useQuestionApi'

export const useQuestionsStore = defineStore('questions', () => {
  /** 当前可见题目列表 */
  const questions = ref<QuestionRecord[]>([])

  /** 当前操作者（auth store） */
  function viewer() {
    const auth = useAuthStore()
    const user = auth.currentUser
    if (!user) return null
    return { username: user.username, role: user.role }
  }

  /** 加载列表（登录后 / 操作后调用） */
  function load(): void {
    const current = viewer()
    if (!current) return
    questions.value = listQuestions(current)
  }

  /** 创建题目（草稿） */
  function create(input: QuestionInput): QuestionRecord | null {
    const current = viewer()
    if (!current) return null
    const record = createQuestion(current.username, input)
    load()
    return record
  }

  /** 编辑题目 */
  function update(id: string, patch: Partial<QuestionInput>): { ok: boolean; error?: string } {
    const current = viewer()
    if (!current) return { ok: false, error: '未登录' }
    const result = updateQuestion(current, id, patch)
    load()
    return result
  }

  /** 删除题目 */
  function remove(id: string): boolean {
    const current = viewer()
    if (!current) return false
    const ok = deleteQuestion(current, id)
    load()
    return ok
  }

  /** 提交审核 */
  function submit(id: string): { ok: boolean; error?: string } {
    const current = viewer()
    if (!current) return { ok: false, error: '未登录' }
    const result = submitForReview(current, id)
    load()
    return result
  }

  /** 管理员审核 */
  function review(id: string, approved: boolean, note?: string): { ok: boolean; error?: string } {
    const current = viewer()
    if (!current) return { ok: false, error: '未登录' }
    const result = reviewQuestion(current, id, approved, note)
    load()
    return result
  }

  /** 导出已发布题库（下载 / 复制） */
  function exportPublished() {
    return exportPublishedQuestions()
  }

  return { questions, load, create, update, remove, submit, review, exportPublished }
})
