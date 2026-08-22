<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { isValidGroup, type EntityRecord } from '@ellia/puzzle-schema'

import { syncClient } from '../../client/ws'
import { useAuthStore } from '../../stores/auth'
import { useLocksStore } from '../../stores/locks'
import ConfirmDialog from '../ui/ConfirmDialog.vue'
import ModalDialog from '../ui/ModalDialog.vue'
import LockOverlay from '../presence/LockOverlay.vue'
import { triggerBlink } from '../../utils/blink'

const props = defineProps<{
  entity: EntityRecord | null
}>()

const emit = defineEmits<{
  (e: 'deleted', entityId: string): void
}>()

const auth = useAuthStore()
const locks = useLocksStore()

const busy = ref(false)
const message = ref<string | null>(null)
const confirmOpen = ref(false)
const rollbackConfirmOpen = ref(false)
const rollbackErrorOpen = ref(false)
const rollbackErrorMessage = ref('')
const commentDialogOpen = ref(false)
const commentDraft = ref('')
const commentLocked = ref(false)
const resourceIdDialogOpen = ref(false)
const resourceIdDraft = ref('')
const resourceIdLocked = ref(false)
const resourceIdValueRef = ref<HTMLButtonElement | null>(null)
const commentSurfaceRef = ref<HTMLDivElement | null>(null)
const groupDialogOpen = ref(false)
const groupDraft = ref('')
const groupLocked = ref(false)
const groupValueRef = ref<HTMLButtonElement | null>(null)

function requestRollback(): void {
  if (props.entity) rollbackConfirmOpen.value = true
}

async function performRollback(): Promise<void> {
  const entityId = props.entity?.id
  if (!entityId) return
  rollbackConfirmOpen.value = false
  busy.value = true
  message.value = null
  try {
    await syncClient.rollback(entityId)
  } catch (error) {
    const msg = error instanceof Error ? error.message : '回退失败'
    rollbackErrorMessage.value = msg
    rollbackErrorOpen.value = true
  } finally {
    busy.value = false
  }
}

function requestDelete(): void {
  if (props.entity) confirmOpen.value = true
}

async function performDelete(): Promise<void> {
  const entityId = props.entity?.id
  if (!entityId) return
  confirmOpen.value = false
  busy.value = true
  message.value = null
  try {
    await syncClient.delete(entityId)
    emit('deleted', entityId)
  } catch (error) {
    message.value = error instanceof Error ? error.message : '删除失败'
  } finally {
    busy.value = false
  }
}

// ---------- comment editing ----------

const commentPath = computed(() => props.entity ? `${props.entity.id}@comment:` : '')

const commentLockInfo = computed(() => commentPath.value ? locks.holderOf(commentPath.value) : null)
const commentLockedByOther = computed(() =>
  Boolean(commentLockInfo.value && commentLockInfo.value.holder.id !== auth.user?.id),
)

async function openCommentDialog(): Promise<void> {
  if (!props.entity) return
  if (commentLockedByOther.value) return
  busy.value = true
  try {
    await syncClient.lock(props.entity.id, commentPath.value)
    commentLocked.value = true
    commentDraft.value = props.entity.comment ?? ''
    commentDialogOpen.value = true
  } catch (err) {
    message.value = err instanceof Error ? err.message : '无法获取编辑锁'
  } finally {
    busy.value = false
  }
}

async function saveComment(): Promise<void> {
  if (!props.entity || !commentLocked.value) return
  busy.value = true
  message.value = null
  let succeeded = false
  try {
    await syncClient.patch(props.entity.id, commentPath.value, commentDraft.value)
    succeeded = true
    commentDialogOpen.value = false
  } catch (err) {
    message.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    // patch 成功或失败后服务端都会释放锁；失败时需重置本地标记，允许下次重新加锁
    commentLocked.value = false
    if (!succeeded) {
      syncClient.unlock(props.entity.id, commentPath.value).catch(() => undefined)
    }
    busy.value = false
  }
}

function cancelComment(): void {
  commentDialogOpen.value = false
  if (commentLocked.value && props.entity) {
    syncClient.unlock(props.entity.id, commentPath.value).catch(() => undefined)
    commentLocked.value = false
  }
}

// ---------- resource_id editing ----------

const resourceIdPath = computed(() => props.entity ? `${props.entity.id}@resource_id:` : '')
const namespace = computed(() => {
  if (!props.entity) return ''
  const colon = props.entity.resource_id.indexOf(':')
  return colon > 0 ? props.entity.resource_id.slice(0, colon) : ''
})
const idPart = computed(() => {
  if (!props.entity) return ''
  const colon = props.entity.resource_id.indexOf(':')
  return colon > 0 ? props.entity.resource_id.slice(colon + 1) : props.entity.resource_id
})

const resourceIdLockInfo = computed(() => resourceIdPath.value ? locks.holderOf(resourceIdPath.value) : null)
const resourceIdLockedByOther = computed(() =>
  Boolean(resourceIdLockInfo.value && resourceIdLockInfo.value.holder.id !== auth.user?.id),
)

async function openResourceIdDialog(): Promise<void> {
  if (!props.entity) return
  if (resourceIdLockedByOther.value) return
  busy.value = true
  try {
    await syncClient.lock(props.entity.id, resourceIdPath.value)
    resourceIdLocked.value = true
    resourceIdDraft.value = idPart.value
    resourceIdDialogOpen.value = true
  } catch (err) {
    message.value = err instanceof Error ? err.message : '无法获取编辑锁'
  } finally {
    busy.value = false
  }
}

async function saveResourceId(): Promise<void> {
  if (!props.entity || !resourceIdLocked.value) return
  if (!resourceIdDraft.value.trim()) {
    message.value = '资源标识符的 id 部分不能为空'
    return
  }
  busy.value = true
  message.value = null
  let succeeded = false
  try {
    await syncClient.patch(props.entity.id, resourceIdPath.value, `${namespace.value}:${resourceIdDraft.value.trim()}`)
    succeeded = true
    resourceIdDialogOpen.value = false
  } catch (err) {
    message.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    // patch 成功或失败后服务端都会释放锁；失败时需重置本地标记，允许下次重新加锁
    resourceIdLocked.value = false
    if (!succeeded) {
      syncClient.unlock(props.entity.id, resourceIdPath.value).catch(() => undefined)
    }
    busy.value = false
  }
}

function cancelResourceId(): void {
  resourceIdDialogOpen.value = false
  if (resourceIdLocked.value && props.entity) {
    syncClient.unlock(props.entity.id, resourceIdPath.value).catch(() => undefined)
    resourceIdLocked.value = false
  }
}

// ---------- group editing ----------

const groupPath = computed(() => props.entity ? `${props.entity.id}@group:` : '')

const groupLockInfo = computed(() => groupPath.value ? locks.holderOf(groupPath.value) : null)
const groupLockedByOther = computed(() =>
  Boolean(groupLockInfo.value && groupLockInfo.value.holder.id !== auth.user?.id),
)

async function openGroupDialog(): Promise<void> {
  if (!props.entity) return
  if (groupLockedByOther.value) return
  busy.value = true
  try {
    await syncClient.lock(props.entity.id, groupPath.value)
    groupLocked.value = true
    groupDraft.value = props.entity.group
    groupDialogOpen.value = true
  } catch (err) {
    message.value = err instanceof Error ? err.message : '无法获取编辑锁'
  } finally {
    busy.value = false
  }
}

async function saveGroup(): Promise<void> {
  if (!props.entity || !groupLocked.value) return
  const trimmed = groupDraft.value.trim()
  if (!isValidGroup(trimmed)) {
    message.value = '分组必须是 Python 模块名单段（小写字母/下划线开头，仅小写字母、数字、下划线）'
    return
  }
  busy.value = true
  message.value = null
  let succeeded = false
  try {
    await syncClient.patch(props.entity.id, groupPath.value, trimmed)
    succeeded = true
    groupDialogOpen.value = false
  } catch (err) {
    message.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    groupLocked.value = false
    if (!succeeded) {
      syncClient.unlock(props.entity.id, groupPath.value).catch(() => undefined)
    }
    busy.value = false
  }
}

function cancelGroup(): void {
  groupDialogOpen.value = false
  if (groupLocked.value && props.entity) {
    syncClient.unlock(props.entity.id, groupPath.value).catch(() => undefined)
    groupLocked.value = false
  }
}

watch(
  () => props.entity?.id,
  () => {
    message.value = null
  },
)

watch(
  () => [props.entity?.id, props.entity?.resource_id] as const,
  ([newId, newValue], [oldId, oldValue]) => {
    if (newId && newId === oldId && newValue !== oldValue) {
      triggerBlink(resourceIdValueRef.value)
    }
  },
)

watch(
  () => [props.entity?.id, props.entity?.comment] as const,
  ([newId, newValue], [oldId, oldValue]) => {
    if (newId && newId === oldId && newValue !== oldValue) {
      triggerBlink(commentSurfaceRef.value)
    }
  },
)

watch(
  () => [props.entity?.id, props.entity?.group] as const,
  ([newId, newValue], [oldId, oldValue]) => {
    if (newId && newId === oldId && newValue !== oldValue) {
      triggerBlink(groupValueRef.value)
    }
  },
)
</script>

<template>
  <div class="editor-actionbar">
    <template v-if="entity">
      <div class="editor-actionbar__row1">
        <div class="editor-actionbar__resource-id">
          <button
            ref="resourceIdValueRef"
            class="editor-actionbar__rid-btn"
            type="button"
            :disabled="resourceIdLockedByOther || busy"
            @click="openResourceIdDialog"
          >
            {{ entity.resource_id }}
          </button>
          <LockOverlay v-if="resourceIdLockInfo" :username="resourceIdLockInfo.holder.username" />
        </div>
        <div class="editor-actionbar__group">
          <button
            ref="groupValueRef"
            class="editor-actionbar__group-btn"
            type="button"
            :disabled="groupLockedByOther || busy"
            @click="openGroupDialog"
          >
            {{ entity.group }}
          </button>
          <LockOverlay v-if="groupLockInfo" :username="groupLockInfo.holder.username" />
        </div>
        <span class="muted">{{ entity.kind }}</span>
        <span class="muted">v{{ entity.version }} · r{{ entity.revision }}</span>
        <span class="editor-actionbar__spacer" />
        <button class="btn btn--tonal" type="button" :disabled="busy" @click="requestRollback">
          版本回退
        </button>
        <button class="btn btn--text" type="button" :disabled="busy" @click="requestDelete">
          删除
        </button>
      </div>
      <div class="editor-actionbar__row2">
        <div
          ref="commentSurfaceRef"
          class="editor-actionbar__comment-surface"
          :class="{ 'editor-actionbar__comment-surface--empty': !entity.comment }"
        >
          <div class="editor-actionbar__comment-text">
            {{ entity.comment || '无注释' }}
          </div>
          <button
            class="editor-actionbar__comment-edit-btn"
            type="button"
            :disabled="commentLockedByOther || busy"
            :title="entity.comment ? '编辑注释' : '添加注释'"
            @click="openCommentDialog"
          >
            {{ entity.comment ? '编辑' : '添加' }}
          </button>
          <LockOverlay v-if="commentLockInfo" :username="commentLockInfo.holder.username" />
        </div>
      </div>
    </template>
    <span v-else class="muted">没有打开的实体</span>
    <span v-if="message" class="error-text" role="alert">{{ message }}</span>

    <ConfirmDialog
      v-if="entity"
      :open="rollbackConfirmOpen"
      title="版本回退"
      :message="`确定回退实体 ${entity.resource_id} 到上一个版本？此操作不可逆。`"
      confirm-label="回退"
      cancel-label="取消"
      :busy="busy"
      @confirm="performRollback"
      @cancel="rollbackConfirmOpen = false"
    />

    <ConfirmDialog
      v-if="entity"
      :open="confirmOpen"
      title="删除实体"
      :message="`确定删除实体 ${entity.resource_id}？此操作不可恢复。`"
      confirm-label="删除"
      cancel-label="取消"
      danger
      :busy="busy"
      @confirm="performDelete"
      @cancel="confirmOpen = false"
    />

    <ModalDialog
      :open="rollbackErrorOpen"
      title="版本回退失败"
      confirm-label="确定"
      :show-cancel="false"
      @confirm="rollbackErrorOpen = false"
    >
      <p class="modal-message">{{ rollbackErrorMessage }}</p>
    </ModalDialog>

    <!-- comment dialog -->
    <ModalDialog
      :open="commentDialogOpen"
      title="编辑注释"
      confirm-label="保存"
      cancel-label="取消"
      :busy="busy"
      @confirm="saveComment"
      @cancel="cancelComment"
    >
      <div class="comment-dialog">
        <textarea
          v-model="commentDraft"
          class="comment-dialog__textarea"
          rows="6"
          placeholder="输入注释"
          spellcheck="false"
        />
      </div>
    </ModalDialog>

    <!-- resource_id dialog -->
    <ModalDialog
      :open="resourceIdDialogOpen"
      title="修改资源标识符"
      confirm-label="保存"
      cancel-label="取消"
      :busy="busy"
      @confirm="saveResourceId"
      @cancel="cancelResourceId"
    >
      <div class="resource-id-dialog">
        <p class="resource-id-dialog__desc">仅可修改 id 部分，命名空间不可更改。</p>
        <div class="resource-id-dialog__input">
          <span class="resource-id-dialog__prefix">{{ namespace }}:</span>
          <input
            v-model="resourceIdDraft"
            class="resource-id-dialog__field"
            type="text"
            placeholder="输入 id 部分"
          />
        </div>
      </div>
    </ModalDialog>

    <!-- group dialog -->
    <ModalDialog
      :open="groupDialogOpen"
      title="修改分组"
      confirm-label="保存"
      cancel-label="取消"
      :busy="busy"
      @confirm="saveGroup"
      @cancel="cancelGroup"
    >
      <div class="group-dialog">
        <p class="group-dialog__desc">分组是导出时的 Python 模块名单段。</p>
        <input
          v-model="groupDraft"
          class="group-dialog__field"
          type="text"
          placeholder="例如 main、chapter1"
        />
      </div>
    </ModalDialog>
  </div>
</template>

<style scoped>
.editor-actionbar {
  display: flex;
  flex-direction: column;
  padding: 6px 10px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  min-height: 44px;
  gap: 6px;
}

.editor-actionbar__row1 {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: nowrap;
  overflow-x: auto;
}

.editor-actionbar__row1 > * {
  flex: none;
}

.editor-actionbar__row2 {
  display: flex;
  align-items: stretch;
  min-width: 0;
}

.editor-actionbar__resource-id {
  position: relative;
  display: inline-flex;
}

.editor-actionbar__rid-btn {
  min-height: 32px;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color 300ms ease,
    border-color 300ms ease;
}

.editor-actionbar__rid-btn:hover {
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.editor-actionbar__rid-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.editor-actionbar__group {
  position: relative;
  display: inline-flex;
}

.editor-actionbar__group-btn {
  min-height: 32px;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font-size: 0.8rem;
  cursor: pointer;
  transition:
    background-color 300ms ease,
    border-color 300ms ease;
}

.editor-actionbar__group-btn:hover {
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.editor-actionbar__group-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.editor-actionbar__comment-surface {
  position: relative;
  flex: 1;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  min-width: 0;
  padding: 6px 10px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
}

.editor-actionbar__comment-surface--empty {
  border-style: dashed;
  opacity: 0.62;
}

.editor-actionbar__comment-text {
  flex: 1;
  min-width: 0;
  font-size: 0.8rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.4;
}

.editor-actionbar__comment-edit-btn {
  flex: none;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font-size: 0.75rem;
  cursor: pointer;
}

.editor-actionbar__comment-edit-btn:hover {
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.editor-actionbar__comment-edit-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.editor-actionbar__spacer {
  flex: 1;
}

.modal-message {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
}

.comment-dialog__textarea {
  width: 100%;
  min-height: 120px;
  padding: 6px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
  font-size: 0.85rem;
  resize: vertical;
}

.resource-id-dialog__desc {
  margin: 0 0 8px;
  font-size: 0.8rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.resource-id-dialog__input {
  display: flex;
  align-items: center;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  overflow: hidden;
}

.resource-id-dialog__prefix {
  flex: none;
  padding: 0 0 0 8px;
  font-size: 0.85rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font-weight: 600;
}

.resource-id-dialog__field {
  flex: 1;
  min-width: 0;
  min-height: 32px;
  padding: 0.3rem 0.6rem;
  border: none;
  background: transparent;
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
  font-size: 0.85rem;
}

.resource-id-dialog__field:focus-visible {
  outline: none;
}

.group-dialog__desc {
  margin: 0 0 8px;
  font-size: 0.8rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.group-dialog__field {
  width: 100%;
  min-height: 32px;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
  font-size: 0.85rem;
}

.group-dialog__field:focus-visible {
  outline: 2px solid var(--md-sys-color-primary, #6750a4);
  outline-offset: 1px;
}
</style>