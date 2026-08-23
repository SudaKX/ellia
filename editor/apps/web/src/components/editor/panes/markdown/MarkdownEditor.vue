<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import type {
  EntityRecord,
  MarkdownSegment,
  MarkdownState,
  UpdateMessage,
} from '@ellia/puzzle-schema'

import { syncClient } from '../../../../client/ws'
import { useEntitiesStore } from '../../../../stores/entities'
import { useLocksStore } from '../../../../stores/locks'
import MarkdownSegmentCard from './MarkdownSegmentCard.vue'
import { moveSegmentInSort, sortedSegments } from './useMarkdown'

const props = defineProps<{
  entity: EntityRecord
}>()

const entitiesStore = useEntitiesStore()
const locks = useLocksStore()

locks.ensureSubscriptions()
onMounted(() => locks.ensureSubscriptions())

const state = computed(() => props.entity.state as unknown as MarkdownState)
const segments = computed(() => sortedSegments(state.value))
const sortPath = computed(() => `${props.entity.id}@state:/sort`)
const error = ref<string | null>(null)
let errorTimer: ReturnType<typeof setTimeout> | null = null

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

async function addSegment(): Promise<void> {
  const id = crypto.randomUUID()
  const segment: MarkdownSegment = { id, content: '' }
  const segmentPath = `${props.entity.id}@state:/segments/${id}`
  const nextSort = [...state.value.sort, id]

  let segmentLocked = false
  let sortLocked = false
  try {
    await syncClient.lock(props.entity.id, segmentPath)
    segmentLocked = true
    const appliedSegment = await syncClient.patch(props.entity.id, segmentPath, segment)
    applyLocalPatch(segmentPath, 'set', segment, appliedSegment.revision, appliedSegment.version)
    segmentLocked = false

    await syncClient.lock(props.entity.id, sortPath.value)
    sortLocked = true
    const appliedSort = await syncClient.patch(props.entity.id, sortPath.value, nextSort)
    applyLocalPatch(sortPath.value, 'set', nextSort, appliedSort.revision, appliedSort.version)
    sortLocked = false
  } catch (err) {
    showError(err instanceof Error ? err.message : '添加段落失败')
  } finally {
    if (segmentLocked) {
      syncClient.unlock(props.entity.id, segmentPath).catch(() => undefined)
    }
    if (sortLocked) {
      syncClient.unlock(props.entity.id, sortPath.value).catch(() => undefined)
    }
  }
}

async function saveSegment(segment: MarkdownSegment, content: string): Promise<void> {
  const segmentPath = `${props.entity.id}@state:/segments/${segment.id}`
  const next = { ...segment, content }
  const applied = await syncClient.patch(props.entity.id, segmentPath, next)
  applyLocalPatch(segmentPath, 'set', next, applied.revision, applied.version)
}

async function deleteSegment(segment: MarkdownSegment): Promise<void> {
  const segmentPath = `${props.entity.id}@state:/segments/${segment.id}`
  const nextSort = state.value.sort.filter((id) => id !== segment.id)

  const appliedRemove = await syncClient.removeField(props.entity.id, segmentPath)
  applyLocalPatch(segmentPath, 'remove', undefined, appliedRemove.revision, appliedRemove.version)

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

async function moveSegment(segment: MarkdownSegment, direction: -1 | 1): Promise<void> {
  const nextSort = moveSegmentInSort(state.value.sort, segment.id, direction)
  if (!nextSort) return

  const segmentPath = `${props.entity.id}@state:/segments/${segment.id}`
  let sortLocked = false
  try {
    await syncClient.lock(props.entity.id, sortPath.value)
    sortLocked = true
    const appliedSort = await syncClient.patch(props.entity.id, sortPath.value, nextSort)
    applyLocalPatch(sortPath.value, 'set', nextSort, appliedSort.revision, appliedSort.version)
    sortLocked = false

    // patch 会自动释放 sort 锁；重新获取 segment 锁，让卡片可以继续编辑当前段。
    await syncClient.lock(props.entity.id, segmentPath)
  } catch (err) {
    if (sortLocked) {
      syncClient.unlock(props.entity.id, sortPath.value).catch(() => undefined)
    }
    throw err
  }
}

onBeforeUnmount(() => {
  if (errorTimer) clearTimeout(errorTimer)
})
</script>

<template>
  <div class="markdown-editor">
    <p v-if="error" class="error-text" role="alert">{{ error }}</p>

    <TransitionGroup
      name="md-segment"
      tag="div"
      class="markdown-editor__segments"
    >
      <MarkdownSegmentCard
        v-for="(segment, index) in segments"
        :key="segment.id"
        :entity="entity"
        :segment="segment"
        :is-first="index === 0"
        :is-last="index === segments.length - 1"
        :on-save="(content) => saveSegment(segment, content)"
        :on-delete="() => deleteSegment(segment)"
        :on-move="(direction) => moveSegment(segment, direction)"
      />
    </TransitionGroup>

    <button
      class="markdown-editor__fab btn btn--primary"
      type="button"
      @click="addSegment"
    >
      ＋ 添加段落
    </button>
  </div>
</template>

<style scoped>
.markdown-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
  padding: 12px;
  box-sizing: border-box;
  overflow-y: auto;
}

.markdown-editor__segments {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.markdown-editor__fab {
  position: sticky;
  bottom: 12px;
  align-self: flex-end;
  flex: none;
  margin-top: 12px;
  z-index: 20;
  border-radius: 999px;
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.2);
}

.md-segment-enter-active,
.md-segment-leave-active,
.md-segment-move {
  transition: all 0.2s ease;
}

.md-segment-enter-from,
.md-segment-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.md-segment-leave-active {
  position: absolute;
  width: 100%;
}
</style>
