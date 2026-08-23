<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'

import type {
  ChoiceQuestionData,
  EntityRecord,
  QuestionnaireQuestion,
  QuestionType,
  TextQuestionData,
} from '@ellia/puzzle-schema'

import { syncClient } from '../../../../client/ws'
import { useAuthStore } from '../../../../stores/auth'
import { useLocksStore } from '../../../../stores/locks'
import DropdownSelect from '../../../ui/DropdownSelect.vue'
import LockOverlay from '../../../presence/LockOverlay.vue'
import MarkdownCodeEditor from '../markdown/MarkdownCodeEditor.vue'
import { renderMarkdown } from '../markdown/render'
import ChoiceQuestionEditor from './ChoiceQuestionEditor.vue'
import ChoiceQuestionPreview from './ChoiceQuestionPreview.vue'
import TextQuestionEditor from './TextQuestionEditor.vue'
import TextQuestionPreview from './TextQuestionPreview.vue'

const QUESTION_TYPE_OPTIONS: Array<{ label: string; value: string }> = [
  { label: '选择题', value: 'choice' },
  { label: '填空题', value: 'text' },
]

const props = withDefaults(
  defineProps<{
    entity: EntityRecord
    question: QuestionnaireQuestion
    isFirst?: boolean
    isLast?: boolean
    onSave?: (question: QuestionnaireQuestion) => Promise<void>
    onDelete?: () => Promise<void>
    onMove?: (direction: -1 | 1) => Promise<void>
  }>(),
  {
    isFirst: false,
    isLast: false,
  },
)

const auth = useAuthStore()
const locks = useLocksStore()

locks.ensureSubscriptions()

const lockPath = computed(() => `${props.entity.id}@state:/questions/${props.question.id}`)
const lockInfo = computed(() => locks.holderOf(lockPath.value))
const lockedByOther = computed(
  () => Boolean(lockInfo.value && lockInfo.value.holder.id !== auth.user?.id),
)

const cardRef = ref<HTMLElement | null>(null)
const contentRef = ref<HTMLElement | null>(null)
let resizeObserver: ResizeObserver | null = null

const editing = ref(false)
const busy = ref(false)
const message = ref<string | null>(null)

const draftDescription = ref(props.question.description)
const draftType = ref<QuestionType>(props.question.type)
const draftData = ref<QuestionnaireQuestion['data']>(cloneData(props.question.data))

const renderedDescription = computed(() => renderMarkdown(props.question.description))
const previewIsChoice = computed(() => props.question.type === 'choice')
const draftIsChoice = computed(() => draftType.value === 'choice')

const draftChoiceData = computed<ChoiceQuestionData>({
  get: () => draftData.value as ChoiceQuestionData,
  set: (value: ChoiceQuestionData) => {
    draftData.value = value
  },
})

const draftTextData = computed<TextQuestionData>({
  get: () => draftData.value as TextQuestionData,
  set: (value: TextQuestionData) => {
    draftData.value = value
  },
})

function cloneData(data: QuestionnaireQuestion['data']): QuestionnaireQuestion['data'] {
  return JSON.parse(JSON.stringify(data)) as QuestionnaireQuestion['data']
}

function syncHeight(): void {
  if (!cardRef.value || !contentRef.value) return
  const style = getComputedStyle(cardRef.value)
  const verticalBorder =
    parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth)
  const next = contentRef.value.offsetHeight + verticalBorder
  cardRef.value.style.height = `${next}px`
}

function startObserving(): void {
  stopObserving()
  if (!contentRef.value) return
  resizeObserver = new ResizeObserver(() => syncHeight())
  resizeObserver.observe(contentRef.value)
}

function stopObserving(): void {
  resizeObserver?.disconnect()
  resizeObserver = null
}

async function startEditing(): Promise<void> {
  if (editing.value || lockedByOther.value) return
  busy.value = true
  message.value = null
  try {
    await syncClient.lock(props.entity.id, lockPath.value)
    editing.value = true
    draftDescription.value = props.question.description
    draftType.value = props.question.type
    draftData.value = cloneData(props.question.data)
  } catch (error) {
    message.value = error instanceof Error ? error.message : '无法获取编辑锁'
  } finally {
    busy.value = false
  }
}

async function stopEditing(unlock: boolean): Promise<void> {
  if (unlock && editing.value) {
    await syncClient.unlock(props.entity.id, lockPath.value).catch(() => undefined)
  }
  editing.value = false
}

function onTypeChange(value: string | number): void {
  const nextType = String(value) as QuestionType
  if (nextType === draftType.value) return
  draftType.value = nextType
  draftData.value =
    nextType === 'choice'
      ? { single: true, options: [''] }
      : { format: null }
}

async function save(): Promise<void> {
  if (!editing.value) return
  busy.value = true
  message.value = null
  try {
    const next: QuestionnaireQuestion = {
      id: props.question.id,
      type: draftType.value,
      description: draftDescription.value,
      data: draftData.value,
    }
    await props.onSave?.(next)
    editing.value = false
  } catch (error) {
    message.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    busy.value = false
  }
}

async function remove(): Promise<void> {
  if (!editing.value) return
  busy.value = true
  message.value = null
  try {
    await props.onDelete?.()
    editing.value = false
  } catch (error) {
    message.value = error instanceof Error ? error.message : '删除失败'
  } finally {
    busy.value = false
  }
}

async function move(direction: -1 | 1): Promise<void> {
  if (!editing.value) return
  busy.value = true
  message.value = null
  try {
    await props.onMove?.(direction)
  } catch (error) {
    message.value = error instanceof Error ? error.message : '移动失败'
  } finally {
    busy.value = false
  }
}

function cancel(): void {
  void stopEditing(true)
}

watch(lockedByOther, (value) => {
  if (value && editing.value) {
    void stopEditing(true)
  }
})

onMounted(() => {
  syncHeight()
  startObserving()
})

onActivated(() => {
  syncHeight()
  startObserving()
})

onBeforeUnmount(() => {
  stopObserving()
  if (editing.value) {
    syncClient.unlock(props.entity.id, lockPath.value).catch(() => undefined)
  }
})

onDeactivated(() => {
  stopObserving()
  void stopEditing(true)
})
</script>

<template>
  <div ref="cardRef" class="question-card" :class="{ 'question-card--editing': editing }">
    <div ref="contentRef" class="question-card__content">
      <div v-if="!editing" class="question-card__preview">
        <div class="question-card__description markdown-body" v-html="renderedDescription" />
        <ChoiceQuestionPreview
          v-if="previewIsChoice"
          :data="question.data as ChoiceQuestionData"
        />
        <TextQuestionPreview v-else :data="question.data as TextQuestionData" />
      </div>
      <div v-else class="question-card__editor">
        <div class="question-card__field">
          <span class="question-card__label">题目说明（markdown）</span>
          <div class="question-card__description-editor">
            <MarkdownCodeEditor v-model="draftDescription" />
          </div>
        </div>
        <div class="question-card__field">
          <span class="question-card__label">题型</span>
          <DropdownSelect
            :options="QUESTION_TYPE_OPTIONS"
            :model-value="draftType"
            @update:model-value="onTypeChange"
          />
        </div>
        <ChoiceQuestionEditor v-if="draftIsChoice" v-model="draftChoiceData" />
        <TextQuestionEditor v-else v-model="draftTextData" />
      </div>

      <div class="question-card__probe">
        <button
          v-if="!editing"
          class="question-card__edit-btn btn btn--small btn--tonal"
          type="button"
          :disabled="busy || lockedByOther"
          @click="startEditing"
        >
          {{ lockedByOther ? '已锁定' : '编辑' }}
        </button>
        <div v-else class="question-card__actions">
          <button
            class="btn btn--small btn--text"
            type="button"
            :disabled="busy || isFirst"
            @click="move(-1)"
          >
            上移
          </button>
          <button
            class="btn btn--small btn--text"
            type="button"
            :disabled="busy || isLast"
            @click="move(1)"
          >
            下移
          </button>
          <button class="btn btn--small btn--primary" type="button" :disabled="busy" @click="save">
            确定
          </button>
          <button class="btn btn--small btn--danger" type="button" :disabled="busy" @click="remove">
            删除
          </button>
          <button class="btn btn--small btn--text" type="button" :disabled="busy" @click="cancel">
            取消
          </button>
        </div>
      </div>

      <p v-if="message" class="error-text question-card__error" role="alert">{{ message }}</p>
    </div>

    <LockOverlay
      v-if="lockedByOther && lockInfo"
      :username="lockInfo.holder.username"
    />
  </div>
</template>

<style scoped>
.question-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
  transition: height 0.2s ease;
  border: 0;
  border-top: 1px solid var(--md-sys-color-surface-container-highest, #e6e0e9);
  border-left: 1px solid var(--md-sys-color-surface-container-highest, #e6e0e9);
  border-right: 1px solid var(--md-sys-color-surface-container-highest, #e6e0e9);
  border-radius: 0;
  background: var(--md-sys-color-surface-container, #f3edf7);
}

.question-card:first-child {
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.question-card:last-child {
  border-bottom: 1px solid var(--md-sys-color-surface-container-highest, #e6e0e9);
  border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px;
}

.question-card--editing {
  padding: 0;
  border: 1px solid var(--md-sys-color-primary, #6750a4);
  border-radius: 8px;
}

.question-card--editing:last-child {
  border-bottom: 1px solid var(--md-sys-color-primary, #6750a4);
}

.question-card__content {
  display: flow-root;
  padding: 12px;
}

.question-card__preview {
  min-height: 32px;
}

.question-card__description {
  overflow-wrap: anywhere;
}

.question-card__editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0;
}

.question-card__field {
  display: grid;
  gap: 4px;
}

.question-card__label {
  font-size: 0.8rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.question-card__description-editor {
  height: 180px;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  transition: border-color 0.15s ease;
}

.question-card__probe {
  position: absolute;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  min-height: 24px;
  margin-top: 8px;
}

.question-card--editing .question-card__probe {
  position: relative;
  right: auto;
  bottom: auto;
}

.question-card__edit-btn {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  margin: 32px 8px 8px 32px;
}

.question-card__probe:hover .question-card__edit-btn,
.question-card__probe:focus-within .question-card__edit-btn {
  opacity: 1;
  pointer-events: auto;
}

.question-card__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.question-card__error {
  margin: 0;
}

.question-card :deep(.markdown-body > :first-child) {
  margin-top: 0;
}

.question-card :deep(.markdown-body > :last-child) {
  margin-bottom: 0;
}

.question-card :deep(.markdown-body h1),
.question-card :deep(.markdown-body h2),
.question-card :deep(.markdown-body h3),
.question-card :deep(.markdown-body h4),
.question-card :deep(.markdown-body h5),
.question-card :deep(.markdown-body h6) {
  color: var(--md-sys-color-on-surface, #1d1b20);
  margin: 0.6em 0 0.3em;
  line-height: 1.3;
}

.question-card :deep(.markdown-body p) {
  margin: 0.4em 0;
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.question-card :deep(.markdown-body a) {
  color: var(--md-sys-color-primary, #6750a4);
}

.question-card :deep(.markdown-body code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.85em;
  padding: 0.1em 0.3em;
  border-radius: 4px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.question-card :deep(.markdown-body pre) {
  padding: 8px;
  border-radius: 6px;
  overflow-x: auto;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.question-card :deep(.markdown-body pre code) {
  padding: 0;
  background: transparent;
}

.question-card :deep(.markdown-body blockquote) {
  margin: 0.4em 0;
  padding: 0.2em 0.8em;
  border-left: 3px solid var(--md-sys-color-primary, #6750a4);
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.question-card :deep(.markdown-body ul),
.question-card :deep(.markdown-body ol) {
  margin: 0.4em 0;
  padding-left: 1.4em;
}
</style>
