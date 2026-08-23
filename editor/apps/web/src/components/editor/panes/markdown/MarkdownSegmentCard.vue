<script setup lang="ts">
import { computed, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'

import type { EntityRecord, MarkdownSegment } from '@ellia/puzzle-schema'

import { syncClient } from '../../../../client/ws'
import { useAuthStore } from '../../../../stores/auth'
import { useLocksStore } from '../../../../stores/locks'
import LockOverlay from '../../../presence/LockOverlay.vue'
import MarkdownCodeEditor from './MarkdownCodeEditor.vue'
import { renderMarkdown } from './render'

const props = withDefaults(
  defineProps<{
    entity: EntityRecord
    segment: MarkdownSegment
    isFirst?: boolean
    isLast?: boolean
    onSave?: (content: string) => Promise<void>
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

const lockPath = computed(() => `${props.entity.id}@state:/segments/${props.segment.id}`)
const lockInfo = computed(() => locks.holderOf(lockPath.value))
const lockedByOther = computed(
  () => Boolean(lockInfo.value && lockInfo.value.holder.id !== auth.user?.id),
)

const editing = ref(false)
const draftContent = ref(props.segment.content)
const busy = ref(false)
const message = ref<string | null>(null)

const rendered = computed(() => renderMarkdown(props.segment.content))

async function startEditing(): Promise<void> {
  if (editing.value || lockedByOther.value) return
  busy.value = true
  message.value = null
  try {
    await syncClient.lock(props.entity.id, lockPath.value)
    editing.value = true
    draftContent.value = props.segment.content
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

async function save(): Promise<void> {
  if (!editing.value) return
  busy.value = true
  message.value = null
  try {
    await props.onSave?.(draftContent.value)
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

onBeforeUnmount(() => {
  if (editing.value) {
    syncClient.unlock(props.entity.id, lockPath.value).catch(() => undefined)
  }
})

onDeactivated(() => {
  void stopEditing(true)
})
</script>

<template>
  <div class="md-card" :class="{ 'md-card--editing': editing }">
    <div v-if="!editing" class="md-card__preview markdown-body" v-html="rendered" />
    <div v-else class="md-card__editor">
      <MarkdownCodeEditor v-model="draftContent" />
    </div>

    <LockOverlay
      v-if="lockedByOther && lockInfo"
      :username="lockInfo.holder.username"
    />

    <div class="md-card__probe">
      <button
        v-if="!editing"
        class="md-card__edit-btn btn btn--small btn--tonal"
        type="button"
        :disabled="busy || lockedByOther"
        @click="startEditing"
      >
        {{ lockedByOther ? '已锁定' : '编辑' }}
      </button>
      <div v-else class="md-card__actions">
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

    <p v-if="message" class="error-text md-card__error" role="alert">{{ message }}</p>
  </div>
</template>

<style scoped>
.md-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 12px;
  border: 0;
  border-top: 1px solid var(--md-sys-color-surface-container-highest, #e6e0e9);
  border-left: 1px solid var(--md-sys-color-surface-container-highest, #e6e0e9);
  border-right: 1px solid var(--md-sys-color-surface-container-highest, #e6e0e9);
  border-radius: 0;
  background: var(--md-sys-color-surface-container, #f3edf7);
}

.md-card:first-child {
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.md-card:last-child {
  border-bottom: 1px solid var(--md-sys-color-surface-container-highest, #e6e0e9);
  border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px;
}

.md-card--editing {
  padding: 0;
}

.md-card__preview {
  min-height: 32px;
  overflow-wrap: anywhere;
}

.md-card__editor {
  height: 240px;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.md-card--editing .md-card__editor {
  border: 2px solid var(--md-sys-color-primary, #6750a4);
  border-radius: 6px;
}

.md-card__probe {
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

.md-card--editing .md-card__probe {
  position: relative;
  right: auto;
  bottom: auto;
}

.md-card__edit-btn {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

.md-card__probe:hover .md-card__edit-btn,
.md-card__probe:focus-within .md-card__edit-btn {
  opacity: 1;
  pointer-events: auto;
}

.md-card__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.md-card__error {
  margin: 0;
}

.md-card :deep(.markdown-body > :first-child) {
  margin-top: 0;
}

.md-card :deep(.markdown-body > :last-child) {
  margin-bottom: 0;
}

.md-card :deep(.markdown-body h1),
.md-card :deep(.markdown-body h2),
.md-card :deep(.markdown-body h3),
.md-card :deep(.markdown-body h4),
.md-card :deep(.markdown-body h5),
.md-card :deep(.markdown-body h6) {
  color: var(--md-sys-color-on-surface, #1d1b20);
  margin: 0.6em 0 0.3em;
  line-height: 1.3;
}

.md-card :deep(.markdown-body p) {
  margin: 0.4em 0;
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.md-card :deep(.markdown-body a) {
  color: var(--md-sys-color-primary, #6750a4);
}

.md-card :deep(.markdown-body code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.85em;
  padding: 0.1em 0.3em;
  border-radius: 4px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.md-card :deep(.markdown-body pre) {
  padding: 8px;
  border-radius: 6px;
  overflow-x: auto;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.md-card :deep(.markdown-body pre code) {
  padding: 0;
  background: transparent;
}

.md-card :deep(.markdown-body blockquote) {
  margin: 0.4em 0;
  padding: 0.2em 0.8em;
  border-left: 3px solid var(--md-sys-color-primary, #6750a4);
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.md-card :deep(.markdown-body ul),
.md-card :deep(.markdown-body ol) {
  margin: 0.4em 0;
  padding-left: 1.4em;
}
</style>
