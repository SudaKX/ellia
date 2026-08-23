<script setup lang="ts">
import { computed } from 'vue'

import type { DagState } from '@ellia/puzzle-schema'

import { useAuthStore } from '../../../../stores/auth'
import { useEditorTabsStore } from '../../../../stores/editorTabs'
import { useLocksStore } from '../../../../stores/locks'
import LockOverlay from '../../../presence/LockOverlay.vue'
import type { DagLayoutNode } from './useDag'

const props = defineProps<{
  dagId: string
  node: DagLayoutNode | null
  state: DagState
}>()

const emit = defineEmits<{
  (e: 'edit', node: DagLayoutNode): void
  (e: 'delete', node: DagLayoutNode): void
}>()

const auth = useAuthStore()
const locks = useLocksStore()
const editorTabs = useEditorTabsStore()

const lockPath = computed(() =>
  props.node ? `${props.dagId}@state:/nodes/${props.node.id}` : '',
)

const lockedByOther = computed(() => {
  if (!props.node) return false
  const lock = locks.holderOf(lockPath.value)
  return Boolean(lock && lock.holder.id !== auth.user?.id)
})

const lockHolderName = computed(() => {
  const lock = locks.holderOf(lockPath.value)
  return lock?.holder.username ?? ''
})

function openEntity(): void {
  if (props.node?.entity) editorTabs.openTab(props.node.entity)
}
</script>

<template>
  <aside class="dag-node-info-panel">
    <LockOverlay v-if="lockedByOther" :username="lockHolderName" />

    <template v-if="node">
      <div class="dag-node-info-panel__body">
        <div class="dag-node-info-panel__left">
          <div class="dag-node-info-panel__row">
            <span class="dag-node-info-panel__label">name</span>
            <code>{{ node.name }}</code>
          </div>
          <div class="dag-node-info-panel__row">
            <span class="dag-node-info-panel__label">node id</span>
            <code>{{ node.id }}</code>
          </div>
          <div class="dag-node-info-panel__row">
            <span class="dag-node-info-panel__label">resource_id</span>
            <code>{{ node.entity?.resource_id ?? '—' }}</code>
          </div>
          <div class="dag-node-info-panel__row">
            <span class="dag-node-info-panel__label">comment</span>
            <code>{{ node.entity?.comment || '—' }}</code>
          </div>
        </div>

        <div class="dag-node-info-panel__right">
          <p v-if="node.isMissing" class="dag-node-info-panel__missing" role="alert">
            ⚠️ 未找到对应的 progress-node 实体
          </p>
          <button
            v-if="node.entity"
            class="btn btn--text"
            type="button"
            @click="openEntity"
          >
            打开
          </button>
          <button
            class="btn btn--tonal"
            type="button"
            :disabled="lockedByOther"
            @click="emit('edit', node)"
          >
            编辑
          </button>
          <button
            class="btn btn--danger"
            type="button"
            :disabled="lockedByOther"
            @click="emit('delete', node)"
          >
            删除
          </button>
        </div>
      </div>
    </template>

    <p v-else class="dag-node-info-panel__placeholder">选择节点查看详情</p>
  </aside>
</template>

<style scoped>
.dag-node-info-panel {
  position: relative;
  flex: none;
  padding: 10px 12px;
  border-top: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
  box-sizing: border-box;
}

.dag-node-info-panel__body {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.dag-node-info-panel__left {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 4px;
}

.dag-node-info-panel__right {
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
}

.dag-node-info-panel__right .btn {
  padding-top: 0;
  padding-bottom: 0;
  min-height: 28px;
}

.dag-node-info-panel__row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8rem;
}

.dag-node-info-panel__label {
  flex: none;
  width: 88px;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.dag-node-info-panel__row code {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dag-node-info-panel__missing {
  margin: 0;
  color: var(--md-sys-color-error, #b3261e);
  font-size: 0.8rem;
}

.dag-node-info-panel__placeholder {
  margin: 0;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font-size: 0.8rem;
}
</style>
