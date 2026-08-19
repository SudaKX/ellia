<script setup lang="ts">
import { ref, watch } from 'vue'

import type { EntityRecord } from '@ellia/puzzle-schema'

import ModalDialog from '../../../ui/ModalDialog.vue'
import TextField from '../../../ui/TextField.vue'
import EntityReferenceSelect from './EntityReferenceSelect.vue'
import type { FieldSpec } from './formTypes'

const props = defineProps<{
  open: boolean
  entity: EntityRecord
  fieldSpec: FieldSpec
  dataPath: string
  modelValue: unknown
}>()

const emit = defineEmits<{
  (e: 'confirm', value: unknown): void
  (e: 'cancel'): void
  (e: 'clear'): void
}>()

const draftString = ref('')
const draftNumber = ref('')
const draftBool = ref(false)
const draftArray = ref<unknown[]>([])

function resetDraft(): void {
  const value = props.modelValue
  draftString.value = typeof value === 'string' ? value : ''
  draftNumber.value = typeof value === 'number' ? String(value) : ''
  draftBool.value = Boolean(value)
  draftArray.value = Array.isArray(value) ? [...value] : []
}

watch(
  () => props.open,
  (open) => {
    if (open) resetDraft()
  },
)

function confirm(): void {
  const spec = props.fieldSpec
  if (spec.type === 'string') {
    emit('confirm', draftString.value)
  } else if (spec.type === 'number') {
    emit('confirm', Number(draftNumber.value))
  } else if (spec.type === 'bool') {
    emit('confirm', draftBool.value)
  } else if (spec.type === 'array') {
    emit('confirm', draftArray.value)
  } else {
    emit('confirm', props.modelValue)
  }
}

function addArrayItem(): void {
  const itemSpec = props.fieldSpec.item
  if (!itemSpec) return
  draftArray.value = [...draftArray.value, defaultValueFor(itemSpec)]
}

function removeArrayItem(index: number): void {
  draftArray.value = draftArray.value.filter((_, itemIndex) => itemIndex !== index)
}

function updateArrayItem(index: number, value: unknown): void {
  const next = [...draftArray.value]
  next[index] = value
  draftArray.value = next
}

function defaultValueFor(spec: FieldSpec): unknown {
  switch (spec.type) {
    case 'string':
      return ''
    case 'number':
      return 0
    case 'bool':
      return false
    case 'object':
      return {}
    case 'array':
      return []
    default:
      return ''
  }
}
</script>

<template>
  <ModalDialog
    :open="open"
    :title="`编辑字段：${dataPath.split('@state:')[1] ?? dataPath}`"
    confirm-label="确定"
    cancel-label="取消"
    @confirm="confirm"
    @cancel="emit('cancel')"
  >
    <div class="field-edit-dialog">
      <p class="field-edit-dialog__description">{{ fieldSpec.description }}</p>

      <div v-if="fieldSpec.optional && modelValue !== undefined" class="field-edit-dialog__clear">
        <button class="btn btn--danger btn--small" type="button" @click="emit('clear')">清除字段</button>
      </div>

      <template v-if="fieldSpec.type === 'string'">
        <EntityReferenceSelect
          v-if="fieldSpec.namespace"
          v-model="draftString"
          :namespace="fieldSpec.namespace"
        />
        <textarea
          v-else
          v-model="draftString"
          rows="4"
          class="field-edit-dialog__textarea"
          placeholder="输入值"
        />
      </template>

      <TextField
        v-else-if="fieldSpec.type === 'number'"
        v-model="draftNumber"
        type="number"
        placeholder="输入数值"
      />

      <label v-else-if="fieldSpec.type === 'bool'" class="field-edit-dialog__bool">
        <input v-model="draftBool" type="checkbox" />
        <span>{{ draftBool ? '是' : '否' }}</span>
      </label>

      <div v-else-if="fieldSpec.type === 'array'" class="field-edit-dialog__array">
        <p v-if="!fieldSpec.item" class="error-text">数组字段缺少 item 定义</p>
        <template v-else>
          <div v-for="(item, index) in draftArray" :key="index" class="field-edit-dialog__array-item">
            <template v-if="fieldSpec.item.type === 'string'">
              <TextField
                :model-value="String(item ?? '')"
                @update:model-value="(value: string) => updateArrayItem(index, value)"
              />
            </template>
            <template v-else-if="fieldSpec.item.type === 'number'">
              <TextField
                :model-value="String(item ?? 0)"
                type="number"
                @update:model-value="(value: string) => updateArrayItem(index, Number(value))"
              />
            </template>
            <label v-else-if="fieldSpec.item.type === 'bool'" class="field-edit-dialog__array-bool">
              <input
                type="checkbox"
                :checked="Boolean(item)"
                @change="(event) => updateArrayItem(index, (event.target as HTMLInputElement).checked)"
              />
            </label>
            <button class="btn btn--text btn--small" type="button" @click="removeArrayItem(index)">删除</button>
          </div>
          <button class="btn btn--small btn--tonal" type="button" @click="addArrayItem">添加一项</button>
        </template>
      </div>
    </div>
  </ModalDialog>
</template>

<style scoped>
.field-edit-dialog {
  display: grid;
  gap: 10px;
}

.field-edit-dialog__description {
  margin: 0;
  font-size: 0.8rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.field-edit-dialog__clear {
  display: flex;
  justify-content: flex-end;
}

.field-edit-dialog__textarea {
  width: 100%;
  min-height: 80px;
  padding: 6px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
  font-size: 0.85rem;
  resize: vertical;
}

.field-edit-dialog__bool {
  display: flex;
  align-items: center;
  gap: 8px;
}

.field-edit-dialog__array {
  display: grid;
  gap: 6px;
}

.field-edit-dialog__array-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.field-edit-dialog__array-bool {
  display: flex;
  align-items: center;
}
</style>