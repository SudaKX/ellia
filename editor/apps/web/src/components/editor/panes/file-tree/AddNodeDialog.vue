<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import ModalDialog from '../../../ui/ModalDialog.vue'
import TextField from '../../../ui/TextField.vue'
import EntityReferenceSelect from '../form/EntityReferenceSelect.vue'
import { isValidTreeNodeName } from './useFileTree'

const props = defineProps<{
  open: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  (e: 'confirm', payload: { name: string; isDirectory: boolean; inode: string | null }): void
  (e: 'cancel'): void
}>()

const isDirectory = ref(true)
const name = ref('')
const inode = ref('')

const nameError = computed(() => {
  if (!isValidTreeNodeName(name.value)) return '名称必须是单段路径名，不能包含 / 或 \\，不能是 . / ..'
  return ''
})

const inodeError = computed(() => {
  if (!isDirectory.value && !inode.value) return '文件节点必须选择要引用的 inode 实体'
  return ''
})

const canConfirm = computed(() => !nameError.value && !inodeError.value)

function reset(): void {
  isDirectory.value = true
  name.value = ''
  inode.value = ''
}

watch(
  () => props.open,
  (open) => {
    if (open) reset()
  },
)

function confirm(): void {
  if (!canConfirm.value) return
  emit('confirm', {
    name: name.value.trim(),
    isDirectory: isDirectory.value,
    inode: isDirectory.value ? null : inode.value,
  })
}
</script>

<template>
  <ModalDialog
    :open="open"
    title="添加节点"
    confirm-label="添加"
    :confirm-disabled="!canConfirm"
    @confirm="confirm"
    @cancel="$emit('cancel')"
  >
    <div class="add-node-dialog">
      <div class="add-node-dialog__kind">
        <button
          type="button"
          class="add-node-dialog__kind-btn"
          :class="{ 'add-node-dialog__kind-btn--active': isDirectory }"
          @click="isDirectory = true"
        >
          📁 文件夹
        </button>
        <button
          type="button"
          class="add-node-dialog__kind-btn"
          :class="{ 'add-node-dialog__kind-btn--active': !isDirectory }"
          @click="isDirectory = false"
        >
          📄 文件
        </button>
      </div>

      <label class="add-node-dialog__field">
        <span>名称（路径段）</span>
        <TextField
          :model-value="name"
          placeholder="例如 assets 或 readme.md"
          @update:model-value="(value) => name = value"
        />
        <span v-if="nameError" class="format-hint" role="alert">{{ nameError }}</span>
      </label>

      <label v-if="!isDirectory" class="add-node-dialog__field">
        <span>引用实体（inode）</span>
        <EntityReferenceSelect
          v-model="inode"
          namespace="inode"
          value-as-id
          placeholder="选择 file-node / artifact-node 实体"
        />
        <span v-if="inodeError" class="format-hint" role="alert">{{ inodeError }}</span>
      </label>

      <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    </div>
  </ModalDialog>
</template>

<style scoped>
.add-node-dialog {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.add-node-dialog__kind {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.add-node-dialog__kind-btn {
  min-height: 36px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  cursor: pointer;
  font: inherit;
  font-size: 0.85rem;
}

.add-node-dialog__kind-btn--active {
  border-color: var(--md-sys-color-primary, #6750a4);
  background: var(--md-sys-color-primary-container, #eaddff);
  color: var(--md-sys-color-on-primary-container, #21005d);
  font-weight: 600;
}

.add-node-dialog__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.85rem;
}

.format-hint {
  color: var(--md-sys-color-tertiary, #7d5260);
  font-size: 0.8rem;
}
</style>
