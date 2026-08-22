<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { EntityRecord, FileTreeNode, FileTreeState, UpdateMessage } from '@ellia/puzzle-schema'

import { syncClient } from '../../../../client/ws'
import { useAuthStore } from '../../../../stores/auth'
import { useEditorTabsStore } from '../../../../stores/editorTabs'
import { useEntitiesStore } from '../../../../stores/entities'
import { useLocksStore } from '../../../../stores/locks'
import ModalDialog from '../../../ui/ModalDialog.vue'
import TextField from '../../../ui/TextField.vue'
import LockOverlay from '../../../presence/LockOverlay.vue'
import EntityReferenceSelect from '../form/EntityReferenceSelect.vue'
import { childrenOf, isValidTreeNodeName, nodePath } from './useFileTree'

const props = defineProps<{
  treeId: string
  state: FileTreeState
  node: FileTreeNode | null
  entities: Record<string, EntityRecord>
}>()

const emit = defineEmits<{
  (e: 'delete', node: FileTreeNode): void
}>()

const auth = useAuthStore()
const locks = useLocksStore()
const entitiesStore = useEntitiesStore()
const editorTabs = useEditorTabsStore()

const lockPath = computed(() =>
  props.node ? `${props.treeId}@state:/nodes/${props.node.id}` : '',
)

const entity = computed(() => {
  if (!props.node?.inode) return null
  return props.entities[props.node.inode] ?? null
})

const isRoot = computed(() => Boolean(props.node && props.node.id === props.state.rootId))

const nodeLocked = computed(() => Boolean(props.node && locks.isLocked(props.treeId, lockPath.value)))

const lockedByOther = computed(() => {
  if (!props.node) return false
  const lock = locks.holderOf(lockPath.value)
  return Boolean(lock && lock.holder.id !== auth.user?.id)
})

const lockHolderName = computed(() => {
  const lock = locks.holderOf(lockPath.value)
  return lock?.holder.username ?? ''
})

const pathText = computed(() => (props.node ? nodePath(props.state, props.node.id) : ''))
const copied = ref(false)

async function copyPath(): Promise<void> {
  if (!pathText.value) return
  try {
    await navigator.clipboard.writeText(pathText.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 1500)
  } catch {
    copied.value = false
  }
}

const editDialogOpen = ref(false)
const busy = ref(false)
const message = ref<string | null>(null)
const draftName = ref('')
const draftInode = ref('')

const nameError = computed(() => {
  const name = draftName.value.trim()
  if (!isValidTreeNodeName(name)) return '名称必须是单段路径名，不能包含 / 或 \\，不能是 . / ..'
  return ''
})

const inodeError = computed(() => {
  if (props.node && !props.node.isDirectory && !draftInode.value) {
    return '文件节点必须选择 inode 实体'
  }
  return ''
})

const canSave = computed(() => !nameError.value && !inodeError.value)

watch(
  () => props.node,
  (node) => {
    editDialogOpen.value = false
    message.value = null
    if (node) {
      draftName.value = node.name
      draftInode.value = node.inode ?? ''
    }
  },
)

async function startEditing(): Promise<void> {
  if (!props.node || isRoot.value || lockedByOther.value) return
  message.value = null
  busy.value = true
  try {
    await syncClient.lock(props.treeId, lockPath.value)
    editDialogOpen.value = true
  } catch (error) {
    message.value = error instanceof Error ? error.message : '无法获取编辑锁'
  } finally {
    busy.value = false
  }
}

async function save(): Promise<void> {
  if (!props.node || !editDialogOpen.value) return
  const name = draftName.value.trim()
  if (!isValidTreeNodeName(name)) {
    message.value = nameError.value
    return
  }
  if (!props.node.isDirectory && !draftInode.value) {
    message.value = '文件节点必须选择 inode 实体'
    return
  }

  const siblings = childrenOf(props.state, props.node.parent ?? props.state.rootId)
  if (siblings.some((item) => item.id !== props.node?.id && item.name === name)) {
    message.value = '同级已存在同名节点'
    return
  }

  message.value = null
  busy.value = true
  const nextNode = {
    ...props.node,
    name,
    inode: props.node.isDirectory ? null : draftInode.value,
  }
  try {
    const applied = await syncClient.patch(props.treeId, lockPath.value, nextNode)
    entitiesStore.applyUpdate({
      type: 'update',
      entity_id: props.treeId,
      revision: applied.revision,
      version: applied.version,
      data_path: lockPath.value,
      op: 'set',
      value: nextNode,
      author: { id: '', username: '' },
    } as UpdateMessage)
    editDialogOpen.value = false
  } catch (error) {
    message.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    busy.value = false
  }
}

function cancel(): void {
  if (props.node && editDialogOpen.value) {
    syncClient.unlock(props.treeId, lockPath.value).catch(() => undefined)
  }
  editDialogOpen.value = false
  if (props.node) {
    draftName.value = props.node.name
    draftInode.value = props.node.inode ?? ''
  }
}

function openLinkedEntity(): void {
  if (!entity.value) return
  editorTabs.openTab(entity.value)
}

function requestDelete(): void {
  if (!props.node || isRoot.value || lockedByOther.value) return
  emit('delete', props.node)
}
</script>

<template>
  <aside class="node-info-panel">
    <LockOverlay v-if="lockedByOther" :username="lockHolderName" />

    <template v-if="node">
      <div class="node-info-panel__body">
        <div class="node-info-panel__left">
          <div class="node-info-panel__summary">
            <div class="node-info-panel__row">
              <span class="node-info-panel__label">name</span>
              <code>{{ node.name }}</code>
            </div>
            <div class="node-info-panel__row">
              <span class="node-info-panel__label">类型</span>
              <code>{{ node.isDirectory ? '文件夹' : '文件' }}</code>
            </div>
            <div class="node-info-panel__row">
              <span class="node-info-panel__label">inode</span>
              <code>{{ node.inode ?? '—' }}</code>
            </div>
          </div>

          <div v-if="entity" class="node-info-panel__entity">
            <div class="node-info-panel__row">
              <span class="node-info-panel__label">resource_id</span>
              <code>{{ entity.resource_id }}</code>
            </div>
            <div class="node-info-panel__row">
              <span class="node-info-panel__label">comment</span>
              <code>{{ entity.comment || '—' }}</code>
            </div>
          </div>
          <p v-else-if="node.inode" class="node-info-panel__missing">⚠️ 链接实体不存在或已删除</p>
        </div>

        <div class="node-info-panel__right">
          <p v-if="message && !editDialogOpen" class="error-text" role="alert">{{ message }}</p>

          <template v-if="!isRoot">
            <button
              class="btn btn--tonal"
              type="button"
              :disabled="lockedByOther || busy"
              @click="startEditing"
            >
              编辑
            </button>
            <button
              v-if="entity"
              class="btn btn--text"
              type="button"
              :disabled="busy"
              @click="openLinkedEntity"
            >
              打开
            </button>
            <button
              class="btn btn--text"
              type="button"
              :disabled="busy"
              @click="copyPath"
            >
              {{ copied ? '已复制' : '复制路径' }}
            </button>
            <button
              class="btn btn--danger"
              type="button"
              :disabled="lockedByOther || busy"
              @click="requestDelete"
            >
              删除
            </button>
          </template>
          <p v-else class="node-info-panel__root-hint">根节点不可编辑或删除</p>
        </div>
      </div>
    </template>

    <p v-else class="node-info-panel__placeholder">选择节点查看信息</p>

    <ModalDialog
      :open="editDialogOpen"
      title="编辑节点"
      confirm-label="保存"
      :busy="busy"
      :confirm-disabled="!canSave"
      @confirm="save"
      @cancel="cancel"
    >
      <div class="node-info-panel__edit">
        <label class="node-info-panel__field">
          <span>名称</span>
          <TextField
            :model-value="draftName"
            placeholder="例如 assets 或 readme.md"
            @update:model-value="(value) => draftName = value"
          />
          <span v-if="nameError" class="format-hint" role="alert">{{ nameError }}</span>
        </label>

        <label v-if="node && !node.isDirectory" class="node-info-panel__field">
          <span>inode</span>
          <EntityReferenceSelect
            v-model="draftInode"
            namespace="inode"
            value-as-id
            placeholder="选择 file-node / artifact-node 实体"
          />
          <span v-if="inodeError" class="format-hint" role="alert">{{ inodeError }}</span>
        </label>
        <p v-else-if="node" class="node-info-panel__folder-hint">文件夹不附加 inode</p>

        <p v-if="message" class="error-text" role="alert">{{ message }}</p>
      </div>
    </ModalDialog>
  </aside>
</template>

<style scoped>
.node-info-panel {
  position: relative;
  flex: none;
  padding: 10px 12px;
  border-top: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
  box-sizing: border-box;
}

.node-info-panel__body {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.node-info-panel__left {
  flex: 1;
  min-width: 0;
}

.node-info-panel__right {
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
}

.node-info-panel__right .btn {
  padding-top: 0;
  padding-bottom: 0;
  min-height: 28px;
}

.node-info-panel__summary,
.node-info-panel__entity {
  display: grid;
  gap: 4px;
  margin-bottom: 8px;
}

.node-info-panel__row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8rem;
}

.node-info-panel__label {
  flex: none;
  width: 88px;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.node-info-panel__row code {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-info-panel__missing {
  color: var(--md-sys-color-error, #b3261e);
  font-size: 0.8rem;
}

.node-info-panel__edit {
  display: grid;
  gap: 12px;
}

.node-info-panel__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.85rem;
}

.node-info-panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.node-info-panel__root-hint,
.node-info-panel__folder-hint {
  margin: 0;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font-size: 0.8rem;
}

.format-hint {
  color: var(--md-sys-color-tertiary, #7d5260);
  font-size: 0.8rem;
}
</style>
