<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { DagNode, DagState, EntityRecord, UpdateMessage } from '@ellia/puzzle-schema'

import { syncClient } from '../../../client/ws'
import { useAuthStore } from '../../../stores/auth'
import { useEntitiesStore } from '../../../stores/entities'
import { useLocksStore } from '../../../stores/locks'
import ModalDialog from '../../ui/ModalDialog.vue'
import DagNodeDialog from './dag/DagNodeDialog.vue'
import DagNodeInfoPanel from './dag/DagNodeInfoPanel.vue'
import DagView from './dag/DagView.vue'
import { buildDagLayout, type DagLayoutNode } from './dag/useDag'

const props = defineProps<{
  entity: EntityRecord
}>()

const entitiesStore = useEntitiesStore()
const locks = useLocksStore()
const auth = useAuthStore()

locks.ensureSubscriptions()
onMounted(() => locks.ensureSubscriptions())
onBeforeUnmount(() => {
  if (toastTimer) clearTimeout(toastTimer)
})

const state = computed(() => props.entity.state as unknown as DagState)
const dagId = computed(() => props.entity.id)
const layout = computed(() => buildDagLayout(state.value, entitiesStore.entities))

const lockHolders = computed(() => {
  const holders: Record<string, string> = {}
  const prefix = `${dagId.value}@state:/nodes/`
  for (const lock of locks.lockList) {
    if (lock.entityId !== dagId.value) continue
    if (lock.holder.id === auth.user?.id) continue
    if (lock.dataPath.startsWith(prefix)) {
      holders[lock.dataPath.slice(prefix.length)] = lock.holder.username
    }
  }
  return holders
})

function applyLocalPatch(
  dataPath: string,
  op: 'set' | 'remove',
  value: unknown,
  revision: number,
  version: number,
): void {
  entitiesStore.applyUpdate({
    type: 'update',
    entity_id: dagId.value,
    revision,
    version,
    data_path: dataPath,
    op,
    ...(op === 'set' ? { value } : {}),
    author: { id: '', username: '' },
  } as UpdateMessage)
}

const selectedId = ref<string | null>(null)
const selectedNode = computed<DagLayoutNode | null>(
  () => layout.value.nodes.find((node) => node.id === selectedId.value) ?? null,
)

watch(
  () => layout.value.nodes,
  (nodes) => {
    if (selectedId.value && !nodes.some((node) => node.id === selectedId.value)) {
      selectedId.value = null
    }
  },
)

const toast = ref<string | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(message: string): void {
  toast.value = message
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value = null
    toastTimer = null
  }, 2500)
}

// ---------- Add / Edit ----------
const dialogOpen = ref(false)
const dialogNode = ref<DagLayoutNode | null>(null)
const dialogBusy = ref(false)
const dialogError = ref<string | null>(null)
const dialogLocked = ref(false)
const dialogLockPath = ref('')

function openAddDialog(): void {
  dialogNode.value = null
  dialogError.value = null
  dialogLocked.value = false
  dialogLockPath.value = ''
  dialogOpen.value = true
}

async function openEditDialog(node: DagLayoutNode): Promise<void> {
  const path = `${dagId.value}@state:/nodes/${node.id}`
  const holder = locks.holderOf(path)
  if (holder && holder.holder.id !== auth.user?.id) return
  dialogBusy.value = true
  dialogError.value = null
  try {
    await syncClient.lock(dagId.value, path)
    dialogLocked.value = true
    dialogLockPath.value = path
    dialogNode.value = node
    dialogOpen.value = true
  } catch (error) {
    showToast(error instanceof Error ? error.message : '无法获取编辑锁')
  } finally {
    dialogBusy.value = false
  }
}

function closeDialog(): void {
  if (dialogBusy.value) return
  if (dialogLocked.value && dialogLockPath.value) {
    syncClient.unlock(dagId.value, dialogLockPath.value).catch(() => undefined)
  }
  dialogLocked.value = false
  dialogLockPath.value = ''
  dialogOpen.value = false
  dialogNode.value = null
}

async function confirmDialog(payload: {
  id: string
  name: string
  pnode: string
  successors: string[]
}): Promise<void> {
  const nodeId = payload.id
  if (!payload.name.trim()) {
    dialogError.value = '请填写节点名称'
    return
  }
  if (!payload.pnode.trim()) {
    dialogError.value = '请选择关联的 progress-node 实体'
    return
  }
  const node: DagNode = {
    id: nodeId,
    name: payload.name.trim(),
    pnode: payload.pnode.trim(),
    successors: payload.successors,
  }
  if (new Set(node.successors).size !== node.successors.length) {
    dialogError.value = '后继节点不能重复'
    return
  }
  if (node.successors.includes(nodeId)) {
    dialogError.value = '节点不能指向自身'
    return
  }
  for (const successor of node.successors) {
    if (!state.value.nodes[successor]) {
      dialogError.value = `后继节点不存在: ${successor}`
      return
    }
  }

  const dataPath = `${dagId.value}@state:/nodes/${nodeId}`
  const alreadyLocked = dialogLocked.value
  dialogBusy.value = true
  dialogError.value = null
  let lockedNow = false
  let succeeded = false
  try {
    if (!alreadyLocked) {
      await syncClient.lock(dagId.value, dataPath)
      lockedNow = true
    }
    const applied = await syncClient.patch(dagId.value, dataPath, node)
    applyLocalPatch(dataPath, 'set', node, applied.revision, applied.version)
    succeeded = true
    dialogLocked.value = false
    dialogLockPath.value = ''
    dialogOpen.value = false
    dialogNode.value = null
    selectedId.value = nodeId
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    if (lockedNow && !succeeded) {
      syncClient.unlock(dagId.value, dataPath).catch(() => undefined)
    }
    dialogBusy.value = false
  }
}

// ---------- Delete ----------
const deleteTarget = ref<DagLayoutNode | null>(null)
const deleteBusy = ref(false)
const deleteError = ref<string | null>(null)

function requestDelete(node: DagLayoutNode): void {
  deleteTarget.value = node
  deleteError.value = null
}

function closeDelete(): void {
  if (deleteBusy.value) return
  deleteTarget.value = null
}

async function confirmDelete(): Promise<void> {
  const target = deleteTarget.value
  if (!target) return
  deleteBusy.value = true
  deleteError.value = null

  const dagIdValue = dagId.value
  const targetPath = `${dagIdValue}@state:/nodes/${target.id}`
  const predecessorIds = Object.values(state.value.nodes)
    .filter((node) => node.successors.includes(target.id))
    .map((node) => node.id)
  const entryAffected = state.value.entryIds.includes(target.id)

  const pathsToCheck = [
    targetPath,
    ...predecessorIds.map((id) => `${dagIdValue}@state:/nodes/${id}`),
  ]
  if (entryAffected) pathsToCheck.push(`${dagIdValue}@state:/entryIds`)

  const blocked = pathsToCheck.find((path) => locks.isLocked(dagIdValue, path))
  if (blocked) {
    deleteError.value = '节点或其相关路径已被锁定，不能删除'
    deleteBusy.value = false
    return
  }

  let currentLockedPath: string | null = null
  let succeeded = false
  try {
    currentLockedPath = targetPath
    await syncClient.lock(dagIdValue, targetPath)
    const appliedRemove = await syncClient.removeField(dagIdValue, targetPath)
    applyLocalPatch(targetPath, 'remove', undefined, appliedRemove.revision, appliedRemove.version)
    currentLockedPath = null

    for (const predecessorId of predecessorIds) {
      const currentNode = state.value.nodes[predecessorId]
      if (!currentNode) continue
      const nextNode = {
        ...currentNode,
        successors: currentNode.successors.filter((id) => id !== target.id),
      }
      const path = `${dagIdValue}@state:/nodes/${predecessorId}`
      currentLockedPath = path
      await syncClient.lock(dagIdValue, path)
      const applied = await syncClient.patch(dagIdValue, path, nextNode)
      applyLocalPatch(path, 'set', nextNode, applied.revision, applied.version)
      currentLockedPath = null
    }

    if (entryAffected) {
      const nextEntries = state.value.entryIds.filter((id) => id !== target.id)
      const path = `${dagIdValue}@state:/entryIds`
      currentLockedPath = path
      await syncClient.lock(dagIdValue, path)
      const applied = await syncClient.patch(dagIdValue, path, nextEntries)
      applyLocalPatch(path, 'set', nextEntries, applied.revision, applied.version)
      currentLockedPath = null
    }

    succeeded = true
    if (selectedId.value === target.id) selectedId.value = null
    deleteTarget.value = null
    showToast(`已删除节点 ${target.id}`)
  } catch (error) {
    deleteError.value = error instanceof Error ? error.message : '删除失败'
  } finally {
    if (!succeeded && currentLockedPath) {
      syncClient.unlock(dagIdValue, currentLockedPath).catch(() => undefined)
    }
    deleteBusy.value = false
  }
}
</script>

<template>
  <div class="dag-editor">
    <Transition name="dag-toast">
      <div v-if="toast" class="dag-editor__toast" role="status">{{ toast }}</div>
    </Transition>

    <div class="dag-editor__top">
      <DagView
        :layout="layout"
        :selected-id="selectedId"
        :lock-holders="lockHolders"
        @select="selectedId = $event"
        @add="openAddDialog"
      />
    </div>

    <DagNodeInfoPanel
      :dag-id="dagId"
      :node="selectedNode"
      :state="state"
      @edit="openEditDialog"
      @delete="requestDelete"
    />

    <DagNodeDialog
      :open="dialogOpen"
      :state="state"
      :node="dialogNode"
      :error="dialogError"
      @confirm="confirmDialog"
      @cancel="closeDialog"
    />

    <ModalDialog
      :open="Boolean(deleteTarget)"
      title="删除 DAG 节点"
      confirm-label="删除"
      danger
      :busy="deleteBusy"
      @confirm="confirmDelete"
      @cancel="closeDelete"
    >
      <p v-if="deleteTarget" class="dag-editor__delete-text">
        确认删除节点 <code>{{ deleteTarget.id }}</code>？会同步清理其他节点的后继引用和入口引用。
      </p>
      <p v-if="deleteError" class="error-text" role="alert">{{ deleteError }}</p>
    </ModalDialog>
  </div>
</template>

<style scoped>
.dag-editor {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.dag-editor__top {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.dag-editor__delete-text {
  margin: 0 0 8px;
  font-size: 0.85rem;
}

.dag-editor__toast {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 20;
  max-width: 280px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--md-sys-color-inverse-surface, #322f35);
  color: var(--md-sys-color-inverse-on-surface, #f5eff7);
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.2);
  font-size: 0.85rem;
  pointer-events: none;
}

.dag-toast-enter-active,
.dag-toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.dag-toast-enter-from,
.dag-toast-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
