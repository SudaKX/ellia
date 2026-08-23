<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from 'vue'

import type {
  EntityRecord,
  QuestionnaireQuestion,
  QuestionnaireState,
  UpdateMessage,
} from '@ellia/puzzle-schema'

import { syncClient } from '../../../../client/ws'
import { useAuthStore } from '../../../../stores/auth'
import { useEntitiesStore } from '../../../../stores/entities'
import { useLocksStore } from '../../../../stores/locks'
import LockOverlay from '../../../presence/LockOverlay.vue'
import MarkdownCodeEditor from '../markdown/MarkdownCodeEditor.vue'
import { renderMarkdown } from '../markdown/render'
import QuestionCard from './QuestionCard.vue'
import { moveQuestionInSort, sortedQuestions } from './useQuestionnaire'

const props = defineProps<{
  entity: EntityRecord
}>()

const entitiesStore = useEntitiesStore()
const locks = useLocksStore()
const auth = useAuthStore()

locks.ensureSubscriptions()
onMounted(() => {
  locks.ensureSubscriptions()
  syncDescriptionHeight()
  startDescriptionObserving()
})

onActivated(() => {
  syncDescriptionHeight()
  startDescriptionObserving()
})

const state = computed(() => props.entity.state as unknown as QuestionnaireState)
const questions = computed(() => sortedQuestions(state.value))
const descriptionPath = computed(() => `${props.entity.id}@state:/description`)
const sortPath = computed(() => `${props.entity.id}@state:/sort`)

const error = ref<string | null>(null)
let errorTimer: ReturnType<typeof setTimeout> | null = null

const renderedDescription = computed(() => renderMarkdown(state.value.description))

const descriptionLockInfo = computed(() => locks.holderOf(descriptionPath.value))
const descriptionLockedByOther = computed(
  () => Boolean(descriptionLockInfo.value && descriptionLockInfo.value.holder.id !== auth.user?.id),
)
const descriptionCardRef = ref<HTMLElement | null>(null)
const descriptionContentRef = ref<HTMLElement | null>(null)
let descriptionResizeObserver: ResizeObserver | null = null

const descriptionEditing = ref(false)
const descriptionDraft = ref(state.value.description)
const descriptionBusy = ref(false)
const descriptionMessage = ref<string | null>(null)

function syncDescriptionHeight(): void {
  if (!descriptionCardRef.value || !descriptionContentRef.value) return
  const style = getComputedStyle(descriptionCardRef.value)
  const verticalBorder =
    parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth)
  const next = descriptionContentRef.value.offsetHeight + verticalBorder
  descriptionCardRef.value.style.height = `${next}px`
}

function startDescriptionObserving(): void {
  stopDescriptionObserving()
  if (!descriptionContentRef.value) return
  descriptionResizeObserver = new ResizeObserver(() => syncDescriptionHeight())
  descriptionResizeObserver.observe(descriptionContentRef.value)
}

function stopDescriptionObserving(): void {
  descriptionResizeObserver?.disconnect()
  descriptionResizeObserver = null
}

function showError(message: string): void {
  error.value = message
  if (errorTimer) clearTimeout(errorTimer)
  errorTimer = setTimeout(() => {
    error.value = null
  }, 3000)
}

function applyLocalPatch(
  dataPath: string,
  op: 'set' | 'remove',
  value: unknown,
  revision: number,
  version: number,
): void {
  entitiesStore.applyUpdate({
    type: 'update',
    entity_id: props.entity.id,
    revision,
    version,
    data_path: dataPath,
    op,
    ...(op === 'set' ? { value } : {}),
    author: { id: '', username: '' },
  } as UpdateMessage)
}

async function startEditDescription(): Promise<void> {
  if (descriptionEditing.value || descriptionLockedByOther.value) return
  descriptionBusy.value = true
  descriptionMessage.value = null
  try {
    await syncClient.lock(props.entity.id, descriptionPath.value)
    descriptionEditing.value = true
    descriptionDraft.value = state.value.description
  } catch (error) {
    descriptionMessage.value = error instanceof Error ? error.message : '无法获取编辑锁'
  } finally {
    descriptionBusy.value = false
  }
}

async function stopDescriptionEditing(unlock: boolean): Promise<void> {
  if (unlock && descriptionEditing.value) {
    await syncClient.unlock(props.entity.id, descriptionPath.value).catch(() => undefined)
  }
  descriptionEditing.value = false
}

async function saveDescription(): Promise<void> {
  if (!descriptionEditing.value) return
  descriptionBusy.value = true
  descriptionMessage.value = null
  try {
    const applied = await syncClient.patch(
      props.entity.id,
      descriptionPath.value,
      descriptionDraft.value,
    )
    applyLocalPatch(
      descriptionPath.value,
      'set',
      descriptionDraft.value,
      applied.revision,
      applied.version,
    )
    descriptionEditing.value = false
  } catch (error) {
    descriptionMessage.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    descriptionBusy.value = false
  }
}

function cancelDescription(): void {
  void stopDescriptionEditing(true)
}

async function addQuestion(): Promise<void> {
  const id = crypto.randomUUID()
  const question: QuestionnaireQuestion = {
    id,
    type: 'text',
    description: '## 示例问题 \n这是 `markdown` 格式描述。',
    data: { format: '^[A-Za-z0-9_-]+$' },
  }
  const questionPath = `${props.entity.id}@state:/questions/${id}`
  const nextSort = [...state.value.sort, id]

  let questionLocked = false
  let sortLocked = false
  try {
    await syncClient.lock(props.entity.id, questionPath)
    questionLocked = true
    const appliedQuestion = await syncClient.patch(props.entity.id, questionPath, question)
    applyLocalPatch(
      questionPath,
      'set',
      question,
      appliedQuestion.revision,
      appliedQuestion.version,
    )
    questionLocked = false

    await syncClient.lock(props.entity.id, sortPath.value)
    sortLocked = true
    const appliedSort = await syncClient.patch(props.entity.id, sortPath.value, nextSort)
    applyLocalPatch(sortPath.value, 'set', nextSort, appliedSort.revision, appliedSort.version)
    sortLocked = false
  } catch (err) {
    showError(err instanceof Error ? err.message : '添加问题失败')
  } finally {
    if (questionLocked) {
      syncClient.unlock(props.entity.id, questionPath).catch(() => undefined)
    }
    if (sortLocked) {
      syncClient.unlock(props.entity.id, sortPath.value).catch(() => undefined)
    }
  }
}

async function saveQuestion(question: QuestionnaireQuestion): Promise<void> {
  const questionPath = `${props.entity.id}@state:/questions/${question.id}`
  const applied = await syncClient.patch(props.entity.id, questionPath, question)
  applyLocalPatch(questionPath, 'set', question, applied.revision, applied.version)
}

async function deleteQuestion(question: QuestionnaireQuestion): Promise<void> {
  const questionPath = `${props.entity.id}@state:/questions/${question.id}`
  const nextSort = state.value.sort.filter((id) => id !== question.id)

  const appliedRemove = await syncClient.removeField(props.entity.id, questionPath)
  applyLocalPatch(
    questionPath,
    'remove',
    undefined,
    appliedRemove.revision,
    appliedRemove.version,
  )

  let sortLocked = false
  try {
    await syncClient.lock(props.entity.id, sortPath.value)
    sortLocked = true
    const appliedSort = await syncClient.patch(props.entity.id, sortPath.value, nextSort)
    applyLocalPatch(sortPath.value, 'set', nextSort, appliedSort.revision, appliedSort.version)
    sortLocked = false
  } catch (err) {
    if (sortLocked) {
      syncClient.unlock(props.entity.id, sortPath.value).catch(() => undefined)
    }
    throw err
  }
}

async function moveQuestion(
  question: QuestionnaireQuestion,
  direction: -1 | 1,
): Promise<void> {
  const nextSort = moveQuestionInSort(state.value.sort, question.id, direction)
  if (!nextSort) return

  const questionPath = `${props.entity.id}@state:/questions/${question.id}`
  let sortLocked = false
  try {
    await syncClient.lock(props.entity.id, sortPath.value)
    sortLocked = true
    const appliedSort = await syncClient.patch(props.entity.id, sortPath.value, nextSort)
    applyLocalPatch(sortPath.value, 'set', nextSort, appliedSort.revision, appliedSort.version)
    sortLocked = false

    // patch 会自动释放 sort 锁；重新获取 question 锁，让卡片可以继续编辑当前题。
    await syncClient.lock(props.entity.id, questionPath)
  } catch (err) {
    if (sortLocked) {
      syncClient.unlock(props.entity.id, sortPath.value).catch(() => undefined)
    }
    throw err
  }
}

onBeforeUnmount(() => {
  stopDescriptionObserving()
  if (errorTimer) clearTimeout(errorTimer)
  if (descriptionEditing.value) {
    syncClient.unlock(props.entity.id, descriptionPath.value).catch(() => undefined)
  }
})

onDeactivated(() => {
  stopDescriptionObserving()
  void stopDescriptionEditing(true)
})
</script>

<template>
  <div class="questionnaire-editor">
    <p v-if="error" class="error-text" role="alert">{{ error }}</p>

    <div
      ref="descriptionCardRef"
      class="questionnaire-editor__description-card"
      :class="{ 'questionnaire-editor__description-card--editing': descriptionEditing }"
    >
      <div ref="descriptionContentRef" class="questionnaire-editor__description-content">
        <div
          v-if="!descriptionEditing"
          class="questionnaire-editor__description-preview markdown-body"
          v-html="renderedDescription"
        />
        <div v-else class="questionnaire-editor__description-editor">
          <MarkdownCodeEditor v-model="descriptionDraft" />
        </div>

        <div class="questionnaire-editor__description-probe">
          <button
            v-if="!descriptionEditing"
            class="questionnaire-editor__description-edit-btn btn btn--small btn--tonal"
            type="button"
            :disabled="descriptionBusy || descriptionLockedByOther"
            @click="startEditDescription"
          >
            {{ descriptionLockedByOther ? '已锁定' : '编辑说明' }}
          </button>
          <div v-else class="questionnaire-editor__description-actions">
            <button
              class="btn btn--small btn--primary"
              type="button"
              :disabled="descriptionBusy"
              @click="saveDescription"
            >
              确定
            </button>
            <button
              class="btn btn--small btn--text"
              type="button"
              :disabled="descriptionBusy"
              @click="cancelDescription"
            >
              取消
            </button>
          </div>
        </div>

        <p v-if="descriptionMessage" class="error-text" role="alert">{{ descriptionMessage }}</p>
      </div>

      <LockOverlay
        v-if="descriptionLockedByOther && descriptionLockInfo"
        :username="descriptionLockInfo.holder.username"
      />
    </div>

    <TransitionGroup
      name="question"
      tag="div"
      class="questionnaire-editor__questions"
    >
      <QuestionCard
        v-for="(question, index) in questions"
        :key="question.id"
        :entity="entity"
        :question="question"
        :is-first="index === 0"
        :is-last="index === questions.length - 1"
        :on-save="(next) => saveQuestion(next)"
        :on-delete="() => deleteQuestion(question)"
        :on-move="(direction) => moveQuestion(question, direction)"
      />
    </TransitionGroup>

    <button
      class="questionnaire-editor__fab btn btn--primary"
      type="button"
      @click="addQuestion"
    >
      ＋ 添加问题
    </button>
  </div>
</template>

<style scoped>
.questionnaire-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
  padding: 12px;
  box-sizing: border-box;
  overflow-y: auto;
}

.questionnaire-editor__description-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
  border: 1px solid var(--md-sys-color-surface-container-highest, #e6e0e9);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  transition: height 0.2s ease;
}

.questionnaire-editor__description-card--editing {
  padding: 0;
  border: 1px solid var(--md-sys-color-primary, #6750a4);
  border-radius: 8px;
}

.questionnaire-editor__description-content {
  display: flow-root;
  min-width: 0;
  padding: 12px;
}

.questionnaire-editor__description-preview {
  min-height: 32px;
  overflow-wrap: anywhere;
}

.questionnaire-editor__description-editor {
  height: 160px;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.questionnaire-editor__description-probe {
  position: absolute;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  min-height: 24px;
  padding: 4px 8px;
}

.questionnaire-editor__description-card--editing .questionnaire-editor__description-probe {
  position: relative;
  right: auto;
  bottom: auto;
}

.questionnaire-editor__description-edit-btn {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

.questionnaire-editor__description-probe:hover .questionnaire-editor__description-edit-btn,
.questionnaire-editor__description-probe:focus-within .questionnaire-editor__description-edit-btn {
  opacity: 1;
  pointer-events: auto;
}

.questionnaire-editor__description-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.questionnaire-editor__questions {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.questionnaire-editor__fab {
  position: sticky;
  bottom: 12px;
  align-self: flex-end;
  flex: none;
  margin-top: 12px;
  z-index: 20;
  border-radius: 999px;
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.2);
}

.question-enter-active,
.question-leave-active,
.question-move {
  transition: all 0.2s ease;
}

.question-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}

.question-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

.question-leave-active {
  position: absolute;
  width: 100%;
}
</style>
