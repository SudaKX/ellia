<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  type EntityRecord,
  type FileTreeNode,
  type FileTreeState,
  type UpdateMessage,
} from '@ellia/puzzle-schema'

import { syncClient } from '../../../client/ws'
import { useEntitiesStore } from '../../../stores/entities'
import { useLocksStore } from '../../../stores/locks'
import ModalDialog from '../../ui/ModalDialog.vue'
import AddNodeDialog from './file-tree/AddNodeDialog.vue'
import FileTreeView from './file-tree/FileTreeView.vue'
import NodeInfoPanel from './file-tree/NodeInfoPanel.vue'
import { childrenOf, descendantIds, nextOrder, nodePath } from './file-tree/useFileTree'

const props = defineProps<{
  entity: EntityRecord
}>()

const entitiesStore = useEntitiesStore()
const locks = useLocksStore()

locks.ensureSubscriptions()
onMounted(() => locks.ensureSubscriptions())
onBeforeUnmount(() => {
  if (toastTimer) clearTimeout(toastTimer)
})

const state = computed(() => props.entity.state as unknown as FileTreeState)
const treeId = computed(() => props.entity.id)

const lockHolders = computed(() => {
  const holders: Record<string, string> = {}
  const prefix = `${treeId.value}@state:/nodes/`
  for (const lock of locks.lockList) {
    if (lock.entityId !== treeId.value) continue
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
    entity_id: treeId.value,
    revision,
    version,
    data_path: dataPath,
    op,
    ...(op === 'set' ? { value } : {}),
    author: { id: '', username: '' },
  } as UpdateMessage)
}

const selectedNodeId = ref<string | null>(null)
const selectedNode = computed<FileTreeNode | null>(
  () => (selectedNodeId.value ? state.value.nodes[selectedNodeId.value] ?? null : null),
)

/** 记录当前选中节点的路径段；节点被删除时按路径段回退，不依赖旧数据快照。 */
const selectedPathSegments = ref<string[]>([])

function pathSegmentsFor(nodeId: string): string[] {
  const path = nodePath(state.value, nodeId)
  return path === '/' ? [] : path.slice(1).split('/')
}

function fallbackBySegments(segments: string[]): string | null {
  let currentId = state.value.rootId
  let lastExisting = state.value.nodes[currentId] ? currentId : null
  for (const segment of segments) {
    const child = childrenOf(state.value, currentId).find((node) => node.name === segment)
    if (!child) break
    lastExisting = child.id
    currentId = child.id
  }
  return lastExisting
}

watch(
  selectedNodeId,
  (id) => {
    if (id && state.value.nodes[id]) {
      selectedPathSegments.value = pathSegmentsFor(id)
    }
  },
  { immediate: true },
)

watch(
  () => state.value.nodes,
  (nodes) => {
    const selected = selectedNodeId.value
    if (!selected) return
    if (nodes[selected]) {
      // 选中节点仍存在时，持续刷新记录的路径，避免重命名后路径过期。
      selectedPathSegments.value = pathSegmentsFor(selected)
      return
    }
    const fallback = fallbackBySegments(selectedPathSegments.value)
    selectedNodeId.value = fallback
    if (fallback) {
      showToast(`节点已删除，已回退到 ${nodePath(state.value, fallback)}`)
    }
  },
  { deep: true },
)

const addDialogOpen = ref(false)
const addParentId = ref<string | null>(null)
const addBusy = ref(false)
const addError = ref<string | null>(null)

const deleteTarget = ref<FileTreeNode | null>(null)
const deleteBusy = ref(false)
const deleteError = ref<string | null>(null)

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

function openAddDialog(parentId: string): void {
  addParentId.value = parentId
  addError.value = null
  addDialogOpen.value = true
}

function closeAddDialog(): void {
  if (addBusy.value) return
  addDialogOpen.value = false
  addParentId.value = null
}

async function confirmAdd(payload: {
  name: string
  isDirectory: boolean
  inode: string | null
}): Promise<void> {
  const parentId = addParentId.value
  if (!parentId) return
  if (childrenOf(state.value, parentId).some((node) => node.name === payload.name)) {
    addError.value = '同级已存在同名节点'
    return
  }
  addBusy.value = true
  addError.value = null

  const treeNodeId = crypto.randomUUID()
  const parentPath = `${treeId.value}@state:/nodes/${parentId}`
  const nodePath = `${treeId.value}@state:/nodes/${treeNodeId}`
  const newNode: FileTreeNode = {
    id: treeNodeId,
    name: payload.name,
    isDirectory: payload.isDirectory,
    inode: payload.inode,
    parent: parentId,
    order: nextOrder(state.value, parentId),
  }

  let parentLocked = false
  let nodeLocked = false
  let succeeded = false
  try {
    await syncClient.lock(treeId.value, parentPath)
    parentLocked = true
    await syncClient.lock(treeId.value, nodePath)
    nodeLocked = true

    const applied = await syncClient.patch(treeId.value, nodePath, newNode)
    applyLocalPatch(nodePath, 'set', newNode, applied.revision, applied.version)

    succeeded = true
    addDialogOpen.value = false
    addParentId.value = null
  } catch (error) {
    addError.value = error instanceof Error ? error.message : '添加节点失败'
  } finally {
    if (nodeLocked && !succeeded) {
      syncClient.unlock(treeId.value, nodePath).catch(() => undefined)
    }
    if (parentLocked) {
      syncClient.unlock(treeId.value, parentPath).catch(() => undefined)
    }
    addBusy.value = false
  }
}

function requestDelete(node: FileTreeNode): void {
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

  const ids = descendantIds(state.value, target.id)
  const blocked = ids.find((id) => locks.isLocked(treeId.value, `${treeId.value}@state:/nodes/${id}`))
  if (blocked) {
    deleteError.value = `节点 ${blocked} 已被锁定，不能删除`
    deleteBusy.value = false
    return
  }

  const selectionAffected = Boolean(selectedNodeId.value && ids.includes(selectedNodeId.value))
  try {
    // 若删除的正是当前选中节点，先回退到其父层，避免编辑器回到根部。
    if (selectionAffected) {
      selectedNodeId.value = target.parent ?? state.value.rootId
    }

    // 从最深层开始移除树节点，避免临时悬空引用影响前端计算。
    const ordered = [...ids].sort((a, b) => {
      const depthA = depthOf(a)
      const depthB = depthOf(b)
      return depthB - depthA
    })
    for (const id of ordered) {
      const path = `${treeId.value}@state:/nodes/${id}`
      await syncClient.lock(treeId.value, path)
      const applied = await syncClient.removeField(treeId.value, path)
      applyLocalPatch(path, 'remove', undefined, applied.revision, applied.version)
    }

    deleteTarget.value = null

    if (selectionAffected) {
      const fallbackId = selectedNodeId.value ?? state.value.rootId
      const fallbackNode = state.value.nodes[fallbackId]
      if (fallbackNode) {
        showToast(`节点已删除，已回退到 ${nodePath(state.value, fallbackId)}`)
      }
    }
  } catch (error) {
    deleteError.value = error instanceof Error ? error.message : '删除失败'
  } finally {
    deleteBusy.value = false
  }
}

function depthOf(nodeId: string): number {
  let depth = 0
  let current = state.value.nodes[nodeId]
  const seen = new Set<string>()
  while (current?.parent && !seen.has(current.id)) {
    seen.add(current.id)
    depth += 1
    current = state.value.nodes[current.parent]
  }
  return depth
}
</script>

<template>
  <div class="file-tree-editor">
    <Transition name="file-tree-toast">
      <div v-if="toast" class="file-tree-editor__toast" role="status">{{ toast }}</div>
    </Transition>

    <div class="file-tree-editor__top">
      <FileTreeView
        :state="state"
        :selected-id="selectedNodeId"
        :lock-holders="lockHolders"
        @select="(nodeId) => selectedNodeId = nodeId"
        @select-parent="(parentId) => selectedNodeId = parentId"
        @add="openAddDialog"
      />
    </div>

    <NodeInfoPanel
      :tree-id="treeId"
      :state="state"
      :node="selectedNode"
      :entities="entitiesStore.entities"
      @delete="requestDelete"
    />

    <AddNodeDialog
      :open="addDialogOpen"
      :error="addError"
      @confirm="confirmAdd"
      @cancel="closeAddDialog"
    />

    <ModalDialog
      :open="Boolean(deleteTarget)"
      title="删除节点"
      confirm-label="删除"
      danger
      :busy="deleteBusy"
      @confirm="confirmDelete"
      @cancel="closeDelete"
    >
      <p v-if="deleteTarget" class="file-tree-editor__delete-text">
        确认删除 <code>{{ deleteTarget.name }}</code> 及其全部子节点？链接的 inode 实体不会被删除。
      </p>
      <p v-if="deleteError" class="error-text" role="alert">{{ deleteError }}</p>
    </ModalDialog>
  </div>
</template>

<style scoped>
.file-tree-editor {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.file-tree-editor__top {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.file-tree-editor__delete-text {
  margin: 0 0 8px;
  font-size: 0.85rem;
}

.file-tree-editor__toast {
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

.file-tree-toast-enter-active,
.file-tree-toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.file-tree-toast-enter-from,
.file-tree-toast-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
