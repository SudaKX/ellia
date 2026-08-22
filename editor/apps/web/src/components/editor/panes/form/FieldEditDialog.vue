<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { EntityRecord } from '@ellia/puzzle-schema'

import ModalDialog from '../../../ui/ModalDialog.vue'
import TextField from '../../../ui/TextField.vue'
import DropdownSelect from '../../../ui/DropdownSelect.vue'
import EntityReferenceSelect from './EntityReferenceSelect.vue'
import FileReferenceSelect from './FileReferenceSelect.vue'
import JsonEditor from './JsonEditor.vue'
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
const draftBitflag = ref(0)
const draftJson = ref('')

const formatError = computed<string | null>(() => {
  const spec = props.fieldSpec
  if (spec.type !== 'string' || !spec.format) return null
  try {
    return new RegExp(spec.format).test(draftString.value) ? null : '格式不符合要求'
  } catch {
    return '格式配置无效'
  }
})

const hasFormatError = computed(() => formatError.value !== null && props.fieldSpec.type === 'string')

const jsonError = computed<string | null>(() => {
  if (props.fieldSpec.type !== 'json') return null
  try {
    JSON.parse(draftJson.value)
    return null
  } catch {
    return 'JSON 格式错误'
  }
})

function resetDraft(): void {
  const value = props.modelValue
  draftString.value = typeof value === 'string' ? value : ''
  draftNumber.value = typeof value === 'number' ? String(value) : ''
  draftBool.value = Boolean(value)
  draftArray.value = Array.isArray(value) ? [...value] : []
  draftBitflag.value = typeof value === 'number' ? value : 0
  draftJson.value = JSON.stringify(value ?? {}, null, 2)
}

watch(
  () => props.open,
  (open) => {
    if (open) resetDraft()
  },
)

function confirm(): void {
  const spec = props.fieldSpec
  if (spec.type === 'string' || spec.type === 'ref' || spec.type === 'file') {
    emit('confirm', draftString.value)
  } else if (spec.type === 'number') {
    emit('confirm', Number(draftNumber.value))
  } else if (spec.type === 'bool') {
    emit('confirm', draftBool.value)
  } else if (spec.type === 'array') {
    emit('confirm', draftArray.value)
  } else if (spec.type === 'bitflag') {
    emit('confirm', draftBitflag.value)
  } else if (spec.type === 'json') {
    emit('confirm', JSON.parse(draftJson.value))
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

function toggleBitflag(index: number, checked: boolean): void {
  const bit = 1 << index
  draftBitflag.value = checked ? draftBitflag.value | bit : draftBitflag.value & ~bit
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
    case 'bitflag':
      return 0
    case 'json':
      return {}
    case 'ref':
      return ''
    case 'file':
      return ''
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
    :confirm-disabled="formatError !== null || jsonError !== null"
    :wide="fieldSpec.type === 'json'"
    @confirm="confirm"
    @cancel="emit('cancel')"
  >
    <div class="field-edit-dialog">
      <p class="field-edit-dialog__description">{{ fieldSpec.description }}</p>

      <div v-if="fieldSpec.optional && modelValue !== undefined" class="field-edit-dialog__clear">
        <button class="btn btn--danger btn--small" type="button" @click="emit('clear')">清除字段</button>
      </div>

      <template v-if="fieldSpec.type === 'ref'">
        <p v-if="!fieldSpec.namespace" class="error-text">ref 字段缺少 namespace 定义</p>
        <EntityReferenceSelect
          v-else
          v-model="draftString"
          :namespace="fieldSpec.namespace"
          value-as-id
        />
      </template>

      <template v-else-if="fieldSpec.type === 'file'">
        <FileReferenceSelect v-model="draftString" />
      </template>

      <template v-else-if="fieldSpec.type === 'string'">
        <DropdownSelect
          v-if="fieldSpec.options"
          v-model="draftString"
          :options="fieldSpec.options"
        />
        <TextField
          v-else-if="fieldSpec.recommends"
          v-model="draftString"
          :recommends="fieldSpec.recommends"
          placeholder="输入或选择"
        />
        <textarea
          v-else
          v-model="draftString"
          rows="4"
          class="field-edit-dialog__textarea"
          :class="{ 'field-edit-dialog__textarea--error': hasFormatError }"
          placeholder="输入值"
        />
        <p v-if="formatError" class="field-edit-dialog__error-text" role="alert">{{ formatError }}</p>
      </template>

      <DropdownSelect
        v-else-if="fieldSpec.type === 'number' && fieldSpec.options"
        :options="fieldSpec.options"
        :model-value="draftNumber"
        @update:model-value="(value) => draftNumber = String(value)"
      />

      <TextField
        v-else-if="fieldSpec.type === 'number'"
        v-model="draftNumber"
        type="number"
        placeholder="输入数值"
      />

      <div v-else-if="fieldSpec.type === 'bool'" class="field-edit-dialog__bool">
        <span class="field-edit-dialog__bool-text">{{ draftBool ? '是' : '否' }}</span>
        <button
          type="button"
          class="field-edit-dialog__switch"
          :class="{ 'field-edit-dialog__switch--on': draftBool }"
          role="switch"
          :aria-checked="draftBool"
          @click="draftBool = !draftBool"
        >
          <span class="field-edit-dialog__switch-thumb" />
        </button>
      </div>

      <div v-else-if="fieldSpec.type === 'bitflag'" class="field-edit-dialog__bitflag">
        <p v-if="!fieldSpec.enums?.length" class="error-text">bitflag 字段缺少 enums 定义</p>
        <template v-else>
          <div class="field-edit-dialog__bitflag-grid">
            <button
              v-for="(label, index) in fieldSpec.enums"
              :key="index"
              type="button"
              class="field-edit-dialog__bitflag-chip"
              :class="{ 'field-edit-dialog__bitflag-chip--checked': (draftBitflag & (1 << index)) !== 0 }"
              :aria-pressed="(draftBitflag & (1 << index)) !== 0"
              @click="toggleBitflag(index, ((draftBitflag & (1 << index)) === 0))"
            >
              <span class="field-edit-dialog__bitflag-label">{{ label }}</span>
              <span class="field-edit-dialog__bitflag-value">{{ 1 << index }}</span>
            </button>
          </div>
          <p class="field-edit-dialog__bitflag-current">当前值：{{ draftBitflag }}</p>
        </template>
      </div>

      <div v-else-if="fieldSpec.type === 'json'" class="field-edit-dialog__json">
        <JsonEditor v-model="draftJson" />
        <p v-if="jsonError" class="field-edit-dialog__error-text" role="alert">{{ jsonError }}</p>
      </div>

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
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.field-edit-dialog > * {
  min-width: 0;
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
  outline: none;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.field-edit-dialog__textarea:focus-visible {
  outline: 2px solid var(--md-sys-color-primary, #6750a4);
  outline-offset: 1px;
}

.field-edit-dialog__textarea--error {
  border-color: var(--md-sys-color-error, #b3261e);
  box-shadow: 0 0 0 2px var(--md-sys-color-error, #b3261e);
}

.field-edit-dialog__textarea--error:focus-visible {
  outline: 2px solid var(--md-sys-color-error, #b3261e);
  outline-offset: 1px;
}

.field-edit-dialog__error-text {
  margin: 0;
  font-size: 0.75rem;
  color: var(--md-sys-color-error, #b3261e);
  line-height: 1.4;
}

.field-edit-dialog__bool {
  display: flex;
  align-items: center;
  gap: 10px;
}

.field-edit-dialog__bool-text {
  font-size: 0.85rem;
  color: var(--md-sys-color-on-surface, #1d1b20);
  min-width: 2em;
}

.field-edit-dialog__switch {
  position: relative;
  width: 36px;
  height: 22px;
  padding: 0;
  box-sizing: border-box;
  border: 2px solid var(--md-sys-color-outline, #79747e);
  border-radius: 999px;
  background: var(--md-sys-color-surface-container-highest, #e6e0e9);
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease;
}

.field-edit-dialog__switch:focus-visible {
  outline: 2px solid var(--md-sys-color-primary, #6750a4);
  outline-offset: 2px;
}

.field-edit-dialog__switch--on {
  background: var(--md-sys-color-primary, #6750a4);
  border-color: var(--md-sys-color-primary, #6750a4);
}

.field-edit-dialog__switch-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--md-sys-color-on-surface-variant, #49454f);
  transition:
    transform 0.2s ease,
    background-color 0.2s ease;
}

.field-edit-dialog__switch--on .field-edit-dialog__switch-thumb {
  transform: translateX(14px);
  background: var(--md-sys-color-on-primary, #ffffff);
}

.field-edit-dialog__json {
  min-width: 0;
}

.field-edit-dialog__bitflag {
  display: grid;
  gap: 8px;
}

.field-edit-dialog__bitflag-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
}

.field-edit-dialog__bitflag-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease;
}

.field-edit-dialog__bitflag-chip--checked {
  border-color: var(--md-sys-color-primary, #6750a4);
  background: var(--md-sys-color-primary-container, #eaddff);
}

.field-edit-dialog__bitflag-label {
  flex: 1;
  font-size: 0.85rem;
}

.field-edit-dialog__bitflag-value {
  font-size: 0.7rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.field-edit-dialog__bitflag-current {
  margin: 0;
  font-size: 0.75rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
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