<script setup lang="ts">
/**
 * # QuestionListView — 题目列表
 *
 * - 普通出题者：仅见本人题目，可编辑 / 删除 / 提交审核 / 测试预览
 * - 管理员：见全部题目，额外可审核（通过 / 驳回）与任意删除
 * - 顶部：状态筛选、"新建题目"、导出已发布题库（供 desktop 自动发现）
 */

import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Check, ClipboardCopy, Download, Pencil, Plus, Trash2 } from 'lucide-vue-next'

import PuzzlePlayer from '@/components/PuzzlePlayer.vue'
import { useAuthStore } from '@/stores/auth'
import { useQuestionsStore } from '@/stores/questions'
import type { QuestionRecord, QuestionStatus } from '@/composables/useQuestionApi'
import type { PuzzleDefinition } from '@/types/puzzle'

const auth = useAuthStore()
const store = useQuestionsStore()
const router = useRouter()

onMounted(() => store.load())

/** 状态筛选（'all' = 全部） */
const filter = ref<'all' | QuestionStatus>('all')

const filteredQuestions = computed(() => {
  if (filter.value === 'all') return store.questions
  return store.questions.filter((question) => question.status === filter.value)
})

/** 状态 → 显示文案 / 颜色 */
const STATUS_META: Record<QuestionStatus, { label: string; tone: 'muted' | 'red' | 'mint' | 'warn' }> = {
  draft: { label: '草稿', tone: 'muted' },
  pending: { label: '待审核', tone: 'warn' },
  approved: { label: '已发布', tone: 'mint' },
  rejected: { label: '已驳回', tone: 'red' },
}

function statusClass(status: QuestionStatus) {
  return `question__status--${STATUS_META[status].tone}`
}

function statusLabel(status: QuestionStatus) {
  return STATUS_META[status].label
}

/** 题目记录 → PuzzleDefinition（测试预览用） */
function toDefinition(question: QuestionRecord): PuzzleDefinition {
  return {
    id: question.id,
    title: question.title,
    blocks: question.blocks,
    type: question.type,
    options: question.options,
    fillAnswers: question.fillAnswers,
    hints: question.hints,
    explanation: question.explanation,
  }
}

/** 预览弹层状态 */
const previewQuestion = ref<QuestionRecord | null>(null)
/** 预览时是否显示正确答案（出题者视角） */
const previewReveal = ref(false)

function openPreview(question: QuestionRecord) {
  previewQuestion.value = question
  previewReveal.value = false
}

/** 新建题目 */
function handleCreate() {
  router.push('/questions/new')
}

/** 编辑题目（本人 / admin） */
function handleEdit(question: QuestionRecord) {
  router.push(`/questions/${question.id}`)
}

/** 提交审核（本人） */
function handleSubmit(question: QuestionRecord) {
  const result = store.submit(question.id)
  if (!result.ok) alert(result.error ?? '提交失败')
}

/** 管理员审核 */
function handleReview(question: QuestionRecord, approved: boolean) {
  const note = approved ? undefined : window.prompt('驳回原因（可选）：') ?? undefined
  const result = store.review(question.id, approved, note)
  if (!result.ok) alert(result.error ?? '操作失败')
}

/** 删除（本人 / admin） */
function handleDelete(question: QuestionRecord) {
  if (!window.confirm(`确定删除题目「${question.title}」？`)) return
  store.remove(question.id)
}

/** 导出已发布题库：下载 JSON 文件 */
function handleExport() {
  const payload = store.exportPublished()
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'published-questions.json'
  anchor.click()
  URL.revokeObjectURL(url)
  exportNote.value = `已导出 ${payload.questions.length} 道已发布题目`
}

/** 复制发布 JSON 到剪贴板 */
async function handleCopyExport() {
  const payload = store.exportPublished()
  try {
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2))
    exportNote.value = '已复制到剪贴板'
  } catch {
    exportNote.value = '复制失败，请使用下载'
  }
}

const exportNote = ref<string | null>(null)
</script>

<template>
  <div class="questions">
    <div class="questions__bar">
      <div class="questions__filters">
        <button
          class="questions__filter"
          :class="{ 'questions__filter--active': filter === 'all' }"
          type="button"
          @click="filter = 'all'"
        >
          全部 ({{ store.questions.length }})
        </button>
        <button
          v-for="(meta, status) in STATUS_META"
          :key="status"
          class="questions__filter"
          :class="{ 'questions__filter--active': filter === status }"
          type="button"
          @click="filter = status"
        >
          {{ meta.label }}
          ({{ store.questions.filter((q) => q.status === status).length }})
        </button>
      </div>

      <div class="questions__actions">
        <span v-if="exportNote" class="questions__export-note">{{ exportNote }}</span>
        <button class="questions__btn" type="button" @click="handleCopyExport">
          <ClipboardCopy :size="14" :stroke-width="1.8" /> 复制发布 JSON
        </button>
        <button class="questions__btn" type="button" @click="handleExport">
          <Download :size="14" :stroke-width="1.8" /> 导出已发布题库
        </button>
        <button class="questions__btn questions__btn--primary" type="button" @click="handleCreate">
          <Plus :size="14" :stroke-width="1.8" /> 新建题目
        </button>
      </div>
    </div>

    <p class="questions__hint">
      导出/复制发布 JSON 后，在桌面端（desktop）把
      <code>config/api.ts</code> 的 <code>USE_PUBLISHED_QUESTIONS</code> 置为 true
      并将 URL 指向该文件即可自动发现。
    </p>

    <!-- 空状态 -->
    <div v-if="filteredQuestions.length === 0" class="questions__empty">
      {{ filter === 'all' ? '还没有题目，点击右上角"新建题目"开始。' : '该状态下暂无题目。' }}
    </div>

    <!-- 题目列表 -->
    <ul v-else class="questions__list">
      <li v-for="question in filteredQuestions" :key="question.id" class="question">
        <div class="question__main">
          <div class="question__head">
            <span class="question__title">{{ question.title }}</span>
            <span class="question__status" :class="statusClass(question.status)">
              {{ statusLabel(question.status) }}
            </span>
          </div>
          <div class="question__meta">
            <span>题型：{{ question.type === 'single' ? '单选' : question.type === 'multi' ? '多选' : '填空' }}</span>
            <span v-if="auth.isAdmin">作者：{{ question.authorUsername }}</span>
            <span>更新：{{ new Date(question.updatedAt).toLocaleString() }}</span>
            <span v-if="question.reviewNote" class="question__review-note">
              驳回原因：{{ question.reviewNote }}
            </span>
          </div>
        </div>

        <div class="question__ops">
          <button class="question__op" type="button" title="测试预览" @click="openPreview(question)">
            测试
          </button>
          <button class="question__op" type="button" title="编辑" @click="handleEdit(question)">
            <Pencil :size="14" :stroke-width="1.8" />
          </button>
          <button
            v-if="question.status !== 'approved'"
            class="question__op"
            type="button"
            title="提交审核"
            @click="handleSubmit(question)"
          >
            提交审核
          </button>
          <template v-if="auth.isAdmin && question.status === 'pending'">
            <button
              class="question__op question__op--approve"
              type="button"
              title="通过"
              @click="handleReview(question, true)"
            >
              <Check :size="14" :stroke-width="1.8" />
            </button>
            <button
              class="question__op question__op--reject"
              type="button"
              title="驳回"
              @click="handleReview(question, false)"
            >
              驳回
            </button>
          </template>
          <button class="question__op question__op--danger" type="button" title="删除" @click="handleDelete(question)">
            <Trash2 :size="14" :stroke-width="1.8" />
          </button>
        </div>
      </li>
    </ul>

    <!-- 测试预览弹层 -->
    <div v-if="previewQuestion" class="preview" @click.self="previewQuestion = null">
      <div class="preview__panel">
        <div class="preview__head">
          <span class="preview__title">测试预览</span>
          <label class="preview__reveal">
            <input v-model="previewReveal" type="checkbox" />
            出题者视角（显示答案）
          </label>
          <button class="preview__close" type="button" @click="previewQuestion = null">关闭</button>
        </div>
        <PuzzlePlayer :definition="toDefinition(previewQuestion)" :reveal-answer="previewReveal" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.questions {
  max-width: 960px;
  margin: 0 auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ── 顶部工具栏 ── */
.questions__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.questions__filters {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.questions__filter {
  padding: 6px 12px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-muted);
  background: transparent;
  font: 11px var(--font-mono);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.questions__filter:hover {
  color: var(--text-primary);
}

.questions__filter--active {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}

.questions__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.questions__export-note {
  color: var(--signal-mint);
  font: 11px var(--font-ui);
}

.questions__btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: var(--surface-panel);
  font: 11px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.questions__btn:hover {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}

.questions__btn--primary {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}

.questions__btn--primary:hover {
  background: var(--surface-hover);
}

.questions__hint {
  margin: 0;
  color: var(--text-muted);
  font: 11px/1.7 var(--font-ui);
}

.questions__hint code {
  color: var(--text-secondary);
  font: 10px var(--font-mono);
}

/* ── 列表 ── */
.questions__empty {
  padding: 48px 20px;
  border: 1px dashed var(--line-default);
  color: var(--text-muted);
  font: 13px var(--font-ui);
  text-align: center;
}

.questions__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.question {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  background: var(--surface-raised);
  transition: border-color 0.12s;
}

.question:hover {
  border-color: var(--line-default);
}

.question__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.question__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.question__title {
  color: var(--text-primary);
  font: 600 14px var(--font-ui);
}

.question__status {
  padding: 1px 8px;
  border: 1px solid var(--line-default);
  font: 10px var(--font-mono);
}

.question__status--muted {
  color: var(--text-muted);
  border-color: var(--line-default);
}

.question__status--warn {
  color: #e0b060;
  border-color: #8a6a30;
}

.question__status--mint {
  color: var(--signal-mint);
  border-color: var(--signal-mint);
}

.question__status--red {
  color: var(--signal-red-soft);
  border-color: var(--signal-red-border);
}

.question__meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--text-muted);
  font: 11px var(--font-ui);
}

.question__review-note {
  color: var(--signal-red-soft);
}

.question__ops {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.question__op {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-secondary);
  background: transparent;
  font: 11px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s;
}

.question__op:hover {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}

.question__op--approve:hover {
  border-color: var(--signal-mint);
  color: var(--signal-mint);
}

.question__op--reject,
.question__op--danger:hover {
  border-color: var(--signal-red);
  color: var(--signal-red-soft);
}

/* ── 预览弹层 ── */
.preview {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(13, 13, 16, 0.72);
}

.preview__panel {
  width: min(680px, 100%);
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line-default);
  background: var(--surface-raised);
  box-shadow: 0 18px 56px rgba(0, 0, 0, 0.5);
}

.preview__head {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line-subtle);
}

.preview__title {
  color: var(--text-primary);
  font: 600 12px var(--font-mono);
  text-transform: uppercase;
}

.preview__reveal {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font: 11px var(--font-ui);
  cursor: pointer;
}

.preview__close {
  padding: 4px 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: transparent;
  font: 11px var(--font-ui);
  cursor: pointer;
}

.preview__close:hover {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}

.preview__panel :deep(.puzzle-player) {
  padding: 16px;
  overflow-y: auto;
}
</style>
