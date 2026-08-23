<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { DagState } from '@ellia/puzzle-schema'

import MultiSelectInput from '../../../ui/MultiSelectInput.vue'
import ModalDialog from '../../../ui/ModalDialog.vue'
import EntityReferenceSelect from '../form/EntityReferenceSelect.vue'
import type { DagLayoutNode } from './useDag'

const props = defineProps<{
  open: boolean
  state: DagState
  node: DagLayoutNode | null
  error: string | null
}>()

const emit = defineEmits<{
  (e: 'confirm', payload: { id: string; name: string; pnode: string; successors: string[] }): void
  (e: 'cancel'): void
}>()

const draftId = ref('')
const draftName = ref('')
const draftPnode = ref('')
const draftSuccessors = ref<string[]>([])

const candidateNodes = computed(() =>
  Object.values(props.state.nodes).filter((node) => node.id !== props.node?.id),
)

const successorOptions = computed(() =>
  candidateNodes.value.map((node) => ({
    label: node.name || node.id,
    value: node.id,
  })),
)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    if (props.node) {
      draftId.value = props.node.id
      draftName.value = props.node.node.name
      draftPnode.value = props.node.node.pnode ?? ''
      draftSuccessors.value = [...props.node.node.successors]
    } else {
      draftId.value = crypto.randomUUID()
      draftName.value = ''
      draftPnode.value = ''
      draftSuccessors.value = []
    }
  },
)

function confirm(): void {
  emit('confirm', {
    id: draftId.value,
    name: draftName.value.trim(),
    pnode: draftPnode.value.trim(),
    successors: draftSuccessors.value,
  })
}
</script>

<template>
  <ModalDialog
    :open="open"
    :title="node ? '编辑 DAG 节点' : '添加 DAG 节点'"
    confirm-label="保存"
    @confirm="confirm"
    @cancel="$emit('cancel')"
  >
    <div class="dag-node-dialog">
      <label class="dag-node-dialog__field">
        <span>名称 <em class="dag-node-dialog__required">*</em></span>
        <input
          v-model="draftName"
          class="dag-node-dialog__input"
          type="text"
          placeholder="例如：开始、检查文件、发放奖励"
        />
      </label>

      <div class="dag-node-dialog__field">
        <span>DAG 节点 ID</span>
        <code>{{ draftId || '（生成中…）' }}</code>
      </div>

      <div class="dag-node-dialog__field">
        <span>链接 progress-node 实体 <em class="dag-node-dialog__required">*</em></span>
        <EntityReferenceSelect
          v-model="draftPnode"
          namespace="pnode"
          value-as-id
          searchable
          placeholder="搜索并选择 pnode 实体"
        />
      </div>

      <div class="dag-node-dialog__field">
        <span>后继节点</span>
        <MultiSelectInput
          v-model="draftSuccessors"
          :options="successorOptions"
          placeholder="搜索并选择后继节点"
          search-placeholder="搜索 DAG 节点..."
        />
      </div>

      <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    </div>
  </ModalDialog>
</template>

<style scoped>
.dag-node-dialog {
  display: grid;
  gap: 12px;
}

.dag-node-dialog__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.85rem;
}

.dag-node-dialog__input {
  min-height: 32px;
  padding: 0.25rem 0.6rem;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
  font-size: 0.85rem;
}

.dag-node-dialog__input:focus-visible {
  outline: 2px solid var(--md-sys-color-primary, #6750a4);
  outline-offset: 1px;
}

.dag-node-dialog__required {
  color: var(--md-sys-color-error, #b3261e);
  font-style: normal;
}
</style>
