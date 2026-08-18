<script setup lang="ts">
import { ref, watch } from 'vue'

import type { EntityRecord } from '@ellia/puzzle-schema'

import { syncClient } from '../../client/ws'
import ConfirmDialog from '../ui/ConfirmDialog.vue'

const props = defineProps<{
  entity: EntityRecord | null
}>()

const emit = defineEmits<{
  (e: 'deleted', entityId: string): void
}>()

const busy = ref(false)
const message = ref<string | null>(null)
const confirmOpen = ref(false)
const rollbackConfirmOpen = ref(false)

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
    message.value = error instanceof Error ? error.message : '回退失败'
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

watch(
  () => props.entity?.id,
  () => {
    message.value = null
  },
)
</script>

<template>
  <div class="editor-actionbar">
    <template v-if="entity">
      <span class="editor-actionbar__title">{{ entity.resource_id }}</span>
      <span class="muted">{{ entity.kind }} · v{{ entity.version }} · r{{ entity.revision }}</span>
      <span class="editor-actionbar__spacer" />
      <button class="btn btn--tonal" type="button" :disabled="busy" @click="requestRollback">
        版本回退
      </button>
      <button class="btn btn--text" type="button" :disabled="busy" @click="requestDelete">
        删除
      </button>
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
  </div>
</template>

<style scoped>
.editor-actionbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  min-height: 44px;
  flex-wrap: nowrap;
  overflow-x: auto;
}

.editor-actionbar > * {
  flex: none;
}

.editor-actionbar__title {
  font-weight: 600;
}

.editor-actionbar__spacer {
  flex: 1;
}
</style>