<script setup lang="ts">
/**
 * # QuestionEditorView — 出题 / 编辑
 *
 * - 题面：富媒体块编辑器（文本 / 图片 URL / 视频 URL / 富文本 HTML，增删排序）
 * - 题型：单选 / 多选（2~10 选项 + 标记正确答案）/ 填空（一个或多个空）
 * - 提示：列表编辑器（动态增删）
 * - 答后解析：单行文本
 * - 操作：保存草稿 / 保存并提交审核 / 实时测试预览（可切出题者视角看答案）
 */

import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-vue-next'

import PuzzlePlayer from '@/components/PuzzlePlayer.vue'
import { useAuthStore } from '@/stores/auth'
import { useQuestionsStore } from '@/stores/questions'
import { getQuestion, type QuestionInput } from '@/composables/useQuestionApi'
import type { ContentBlock, PuzzleDefinition, PuzzleOption, QuestionType } from '@/types/puzzle'

const auth = useAuthStore()
const store = useQuestionsStore()
const route = useRoute()
const router = useRouter()

/** 编辑模式下的题目 id（/questions/new 时为 null） */
const editingId = ref<string | null>(typeof route.params.id === 'string' ? route.params.id : null)

onMounted(() => {
  // 编辑模式：加载既有题目；权限校验（本人或 admin）
  if (editingId.value) {
    const record = getQuestion(editingId.value)
    if (!record) {
      router.replace('/questions')
      return
    }
    if (record.authorUsername !== auth.currentUser?.username && !auth.isAdmin) {
      router.replace('/questions')
      return
    }
    title.value = record.title
    type.value = record.type
    blocks.value = record.blocks.map((block) => ({ ...block }))
    options.value = (record.options ?? []).map((option) => ({ ...option }))
    fillAnswers.value = [...(record.fillAnswers ?? [])]
    hints.value = [...(record.hints ?? [])]
    explanation.value = record.explanation ?? ''
  }
  store.load()
})

// ─── 表单状态 ──────────────────────────────────────

const title = ref('')
const type = ref<QuestionType>('single')
const blocks = ref<ContentBlock[]>([])
const options = ref<PuzzleOption[]>([{ text: '', correct: true }, { text: '', correct: false }])
const fillAnswers = ref<string[]>([''])
const hints = ref<string[]>([''])
const explanation = ref('')
const error = ref<string | null>(null)
const previewReveal = ref(false)
const showPreview = ref(false)

/** 实时预览定义 */
const previewDefinition = computed<PuzzleDefinition>(() => ({
  id: editingId.value ?? 'preview',
  title: title.value || '未命名题目',
  blocks: blocks.value,
  type: type.value,
  options: options.value,
  fillAnswers: fillAnswers.value,
  hints: hints.value,
  explanation: explanation.value,
}))

// ─── 题面块编辑器 ──────────────────────────────────

/** 新建一个空块 */
function addBlock() {
  blocks.value.push({ type: 'text', text: '' })
}

/**
 * 切换内容块类型（替换为对应类型的新块，保留位置）。
 * 不能用 v-model 直接绑定 block.type：判别字段可写时 vue-tsc 会放弃
 * 对 ContentBlock 联合类型的收窄，导致模板内字段访问报错。
 */
function setBlockType(block: ContentBlock, next: ContentBlock['type']) {
  if (next === block.type) return
  const index = blocks.value.indexOf(block)
  if (index === -1) return
  const cleared: ContentBlock =
    next === 'text'
      ? { type: 'text', text: '' }
      : next === 'image'
        ? { type: 'image', url: '' }
        : next === 'video'
          ? { type: 'video', url: '' }
          : { type: 'rich', html: '' }
  blocks.value.splice(index, 1, cleared)
}

function removeBlock(index: number) {
  blocks.value.splice(index, 1)
}

/**
 * 更新内容块字段（v-model 无法直接绑定 ContentBlock 联合类型的字段，
 * 用类型收窄的 setter 替代，见模板 @input）。
 */
function setBlockField(block: ContentBlock, field: 'text' | 'url' | 'caption' | 'html', value: string) {
  if (field === 'text' && block.type === 'text') {
    block.text = value
  } else if ((field === 'url' || field === 'caption') && (block.type === 'image' || block.type === 'video')) {
    if (field === 'url') block.url = value
    else block.caption = value
  } else if (field === 'html' && block.type === 'rich') {
    block.html = value
  }
}

function moveBlock(index: number, delta: -1 | 1) {
  const target = index + delta
  if (target < 0 || target >= blocks.value.length) return
  const list = blocks.value
  ;[list[index], list[target]] = [list[target], list[index]]
}

// ─── 选项编辑器（单选/多选）────────────────────────

function addOption() {
  if (options.value.length >= 10) {
    error.value = '选项最多 10 个'
    return
  }
  options.value.push({ text: '', correct: false })
}

function removeOption(index: number) {
  if (options.value.length <= 2) {
    error.value = '选项至少 2 个'
    return
  }
  options.value.splice(index, 1)
  // 单选：若删除的是唯一正确项，自动纠正到第一项
  if (type.value === 'single' && !options.value.some((option) => option.correct)) {
    options.value[0].correct = true
  }
}

function setSingleCorrect(index: number) {
  options.value.forEach((option, i) => {
    option.correct = i === index
  })
}

// ─── 填空答案编辑器 ────────────────────────────────

function addFill() {
  fillAnswers.value.push('')
}

function removeFill(index: number) {
  if (fillAnswers.value.length <= 1) {
    error.value = '填空至少 1 个空'
    return
  }
  fillAnswers.value.splice(index, 1)
}

// ─── 提示编辑器 ────────────────────────────────────

function addHint() {
  hints.value.push('')
}

function removeHint(index: number) {
  hints.value.splice(index, 1)
}

// ─── 校验与保存 ────────────────────────────────────

/** 基础校验，返回是否通过 */
function validate(): boolean {
  error.value = null
  if (!title.value.trim()) {
    error.value = '请填写题目标题'
    return false
  }
  if (blocks.value.length === 0 || blocks.value.every((block) => block.type === 'text' && !block.text.trim())) {
    error.value = '请至少填写一段题面内容'
    return false
  }
  if (type.value === 'single' || type.value === 'multi') {
    const filled = options.value.filter((option) => option.text.trim())
    if (filled.length < 2) {
      error.value = '选择题至少 2 个选项'
      return false
    }
    if (!options.value.some((option) => option.correct)) {
      error.value = '请标记至少一个正确答案'
      return false
    }
  }
  if (type.value === 'fill' && fillAnswers.value.every((answer) => !answer.trim())) {
    error.value = '填空至少填写一个答案'
    return false
  }
  return true
}

/** 组装输入对象 */
function buildInput(): QuestionInput {
  return {
    title: title.value.trim(),
    blocks: blocks.value,
    type: type.value,
    options: type.value === 'single' || type.value === 'multi' ? options.value : undefined,
    fillAnswers: type.value === 'fill' ? fillAnswers.value.map((value) => value.trim()) : undefined,
    hints: hints.value.map((value) => value.trim()).filter(Boolean),
    explanation: explanation.value.trim() || undefined,
  }
}

/** 保存（草稿） */
function handleSaveDraft() {
  if (!validate()) return
  persist(false)
}

/** 保存并提交审核 */
function handleSaveAndSubmit() {
  if (!validate()) return
  const id = persist(true)
  if (id) {
    const result = store.submit(id)
    if (!result.ok) alert(result.error ?? '提交失败')
  }
}

/**
 * 持久化题目。
 *
 * @param markDirty - 是否将状态重置为草稿（提交审核流程用；保存草稿本身即 draft）
 * @returns 题目 id
 */
function persist(_markDirty: boolean): string | null {
  const input = buildInput()
  if (editingId.value) {
    const result = store.update(editingId.value, input)
    if (!result.ok) {
      error.value = result.error ?? '保存失败'
      return null
    }
    return editingId.value
  }
  const record = store.create(input)
  if (!record) {
    error.value = '创建失败'
    return null
  }
  editingId.value = record.id
  router.replace(`/questions/${record.id}`)
  return record.id
}
</script>

<template>
  <div class="editor">
    <div class="editor__grid">
      <!-- 左侧：编辑表单 -->
      <form class="editor__form" @submit.prevent="handleSaveDraft">
        <p class="editor__eyebrow">{{ editingId ? '编辑题目' : '新建题目' }}</p>

        <label class="editor__field">
          <span class="editor__label">题目标题 *</span>
          <input v-model="title" class="editor__input" type="text" placeholder="如：凯撒密码" />
        </label>

        <label class="editor__field">
          <span class="editor__label">题型 *</span>
          <select v-model="type" class="editor__input">
            <option value="single">单选</option>
            <option value="multi">多选</option>
            <option value="fill">填空</option>
          </select>
        </label>

        <!-- 题面块编辑器 -->
        <div class="editor__field">
          <span class="editor__label">题面内容 *</span>
          <div class="editor__blocks">
            <div v-for="(block, index) in blocks" :key="index" class="block">
              <div class="block__head">
                <select
                  :value="block.type"
                  class="block__type"
                  aria-label="块类型"
                  @change="setBlockType(block, ($event.target as HTMLSelectElement).value as ContentBlock['type'])"
                >
                  <option value="text">文本</option>
                  <option value="image">图片</option>
                  <option value="video">视频</option>
                  <option value="rich">富文本</option>
                </select>
                <div class="block__ops">
                  <button class="block__op" type="button" title="上移" @click="moveBlock(index, -1)">
                    <ArrowUp :size="14" :stroke-width="1.8" />
                  </button>
                  <button class="block__op" type="button" title="下移" @click="moveBlock(index, 1)">
                    <ArrowDown :size="14" :stroke-width="1.8" />
                  </button>
                  <button class="block__op block__op--danger" type="button" title="删除" @click="removeBlock(index)">
                    <Trash2 :size="14" :stroke-width="1.8" />
                  </button>
                </div>
              </div>

              <template v-if="block.type === 'text'">
                <textarea
                  :value="block.text"
                  class="editor__textarea"
                  rows="3"
                  placeholder="文本内容"
                  @input="setBlockField(block, 'text', ($event.target as HTMLTextAreaElement).value)"
                ></textarea>
              </template>
              <template v-else-if="block.type === 'image' || block.type === 'video'">
                <input
                  :value="block.url"
                  class="editor__input"
                  type="text"
                  placeholder="媒体 URL"
                  @input="setBlockField(block, 'url', ($event.target as HTMLInputElement).value)"
                />
                <input
                  :value="block.caption"
                  class="editor__input"
                  type="text"
                  placeholder="说明（可选）"
                  @input="setBlockField(block, 'caption', ($event.target as HTMLInputElement).value)"
                />
              </template>
              <template v-else>
                <textarea
                  :value="block.html"
                  class="editor__textarea"
                  rows="4"
                  placeholder="HTML 内容（审核后渲染）"
                  @input="setBlockField(block, 'html', ($event.target as HTMLTextAreaElement).value)"
                ></textarea>
              </template>
            </div>
          </div>
          <button class="editor__btn" type="button" @click="addBlock">
            <Plus :size="14" :stroke-width="1.8" /> 添加内容块
          </button>
        </div>

        <!-- 选项（单选/多选） -->
        <div v-if="type !== 'fill'" class="editor__field">
          <span class="editor__label">
            {{ type === 'single' ? '选项（单选，2~10 个）*' : '选项（多选，2~10 个）*' }}
          </span>
          <div class="editor__options">
            <div v-for="(option, index) in options" :key="index" class="option">
              <label class="option__correct">
                <input
                  v-if="type === 'single'"
                  type="radio"
                  name="correct-option"
                  :checked="option.correct === true"
                  @change="setSingleCorrect(index)"
                />
                <input
                  v-else
                  type="checkbox"
                  :checked="option.correct === true"
                  @change="option.correct = !option.correct"
                />
              </label>
              <input v-model="option.text" class="editor__input" type="text" placeholder="选项文本" />
              <button class="option__remove" type="button" title="删除选项" @click="removeOption(index)">
                <Trash2 :size="14" :stroke-width="1.8" />
              </button>
            </div>
          </div>
          <button class="editor__btn" type="button" @click="addOption">
            <Plus :size="14" :stroke-width="1.8" /> 添加选项
          </button>
        </div>

        <!-- 填空答案 -->
        <div v-else class="editor__field">
          <span class="editor__label">填空答案 *</span>
          <div class="editor__fills">
            <div v-for="(answer, index) in fillAnswers" :key="index" class="fill">
              <span class="fill__label">第 {{ index + 1 }} 空</span>
              <input v-model="fillAnswers[index]" class="editor__input" type="text" placeholder="答案" />
              <button class="fill__remove" type="button" title="删除空" @click="removeFill(index)">
                <Trash2 :size="14" :stroke-width="1.8" />
              </button>
            </div>
          </div>
          <button class="editor__btn" type="button" @click="addFill">
            <Plus :size="14" :stroke-width="1.8" /> 添加空
          </button>
        </div>

        <!-- 提示 -->
        <div class="editor__field">
          <span class="editor__label">提示（逐条揭示，可选）</span>
          <div class="editor__hints">
            <div v-for="(hint, index) in hints" :key="index" class="hint">
              <input v-model="hints[index]" class="editor__input" type="text" placeholder="提示内容" />
              <button class="hint__remove" type="button" title="删除提示" @click="removeHint(index)">
                <Trash2 :size="14" :stroke-width="1.8" />
              </button>
            </div>
          </div>
          <button class="editor__btn" type="button" @click="addHint">
            <Plus :size="14" :stroke-width="1.8" /> 添加提示
          </button>
        </div>

        <label class="editor__field">
          <span class="editor__label">答后解析（可选）</span>
          <input v-model="explanation" class="editor__input" type="text" placeholder="答对后展示的解析" />
        </label>

        <p v-if="error" class="editor__error">{{ error }}</p>

        <div class="editor__actions">
          <button class="editor__btn editor__btn--primary" type="submit">
            保存草稿
          </button>
          <button class="editor__btn" type="button" @click="handleSaveAndSubmit">
            保存并提交审核
          </button>
          <button class="editor__btn" type="button" @click="showPreview = true">
            测试预览
          </button>
        </div>
      </form>

      <!-- 右侧：实时预览 -->
      <aside class="editor__preview">
        <div class="editor__preview-head">
          <span class="editor__preview-title">实时预览</span>
          <label class="editor__preview-reveal">
            <input v-model="previewReveal" type="checkbox" />
            出题者视角（显示答案）
          </label>
        </div>
        <div class="editor__preview-body">
          <PuzzlePlayer :definition="previewDefinition" :reveal-answer="previewReveal" />
        </div>
      </aside>
    </div>

    <!-- 全屏预览弹层 -->
    <div v-if="showPreview" class="editor__modal" @click.self="showPreview = false">
      <div class="editor__modal-panel">
        <div class="editor__modal-head">
          <span>测试预览</span>
          <label>
            <input v-model="previewReveal" type="checkbox" />
            显示答案
          </label>
          <button type="button" @click="showPreview = false">关闭</button>
        </div>
        <PuzzlePlayer :definition="previewDefinition" :reveal-answer="previewReveal" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.editor {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.editor__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 16px;
  align-items: start;
}

.editor__form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  border: 1px solid var(--line-default);
  background: var(--surface-raised);
}

.editor__eyebrow {
  margin: 0;
  color: var(--signal-red-soft);
  font: 700 10px var(--font-mono);
  text-transform: uppercase;
}

.editor__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.editor__label {
  color: var(--text-muted);
  font: 11px var(--font-ui);
}

.editor__input,
.editor__textarea {
  width: 100%;
  min-height: 34px;
  padding: 6px 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: var(--surface-panel);
  font: 13px var(--font-ui);
  outline: none;
  transition: border-color 0.12s;
}

.editor__textarea {
  resize: vertical;
  font: 13px/1.6 var(--font-ui);
}

.editor__input:focus,
.editor__textarea:focus {
  border-color: var(--signal-red-soft);
}

/* 内容块 */
.editor__blocks,
.editor__options,
.editor__fills,
.editor__hints {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  border: 1px solid var(--line-subtle);
  background: var(--surface-panel);
}

.block__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.block__type {
  padding: 3px 6px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: var(--canvas);
  font: 11px var(--font-mono);
}

.block__ops,
.editor__actions {
  display: flex;
  gap: 6px;
}

.block__op,
.editor__btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
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

.block__op:hover,
.editor__btn:hover {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}

.block__op--danger:hover {
  border-color: var(--signal-red);
  color: var(--signal-red-soft);
}

.editor__btn--primary {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}

/* 选项行 */
.option,
.fill,
.hint {
  display: flex;
  align-items: center;
  gap: 8px;
}

.option__correct {
  display: flex;
  align-items: center;
}

.option__remove,
.fill__remove,
.hint__remove {
  display: flex;
  align-items: center;
  padding: 6px;
  border: none;
  color: var(--text-muted);
  background: transparent;
  cursor: pointer;
}

.option__remove:hover,
.fill__remove:hover,
.hint__remove:hover {
  color: var(--signal-red-soft);
}

.fill__label {
  flex-shrink: 0;
  color: var(--text-muted);
  font: 11px var(--font-mono);
}

.editor__error {
  margin: 0;
  color: var(--signal-red);
  font: 12px var(--font-ui);
}

/* 右侧实时预览 */
.editor__preview {
  position: sticky;
  top: 20px;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line-default);
  background: var(--surface-raised);
}

.editor__preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--line-subtle);
}

.editor__preview-title {
  color: var(--text-muted);
  font: 700 10px var(--font-mono);
  text-transform: uppercase;
}

.editor__preview-reveal {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font: 11px var(--font-ui);
  cursor: pointer;
}

.editor__preview-body {
  max-height: calc(100vh - 140px);
  overflow-y: auto;
}

.editor__preview-body :deep(.puzzle-player) {
  padding: 16px;
}

/* 全屏预览弹层 */
.editor__modal {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(13, 13, 16, 0.72);
}

.editor__modal-panel {
  width: min(680px, 100%);
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line-default);
  background: var(--surface-raised);
  box-shadow: 0 18px 56px rgba(0, 0, 0, 0.5);
}

.editor__modal-head {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line-subtle);
  font: 600 12px var(--font-mono);
}

.editor__modal-head label {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font: 11px var(--font-ui);
}

.editor__modal-head button {
  padding: 4px 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: transparent;
  font: 11px var(--font-ui);
  cursor: pointer;
}

.editor__modal-head button:hover {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}

.editor__modal-panel :deep(.puzzle-player) {
  padding: 16px;
  overflow-y: auto;
}

@media (max-width: 900px) {
  .editor__grid {
    grid-template-columns: 1fr;
  }

  .editor__preview {
    position: static;
  }
}
</style>
