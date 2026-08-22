<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { EntityRecord } from '@ellia/puzzle-schema'

import { syncClient } from '../../../../client/ws'
import { useLocksStore } from '../../../../stores/locks'
import LockHint from '../../../presence/LockHint.vue'
import TextField from '../../../ui/TextField.vue'
import type { FieldSpec } from './formTypes'

const props = defineProps<{
  entity: EntityRecord
  fieldSpec: FieldSpec
  dataPath: string
  modelValue: unknown
}>()

const locks = useLocksStore()

const itemSpec = computed<FieldSpec | undefined>(() => props.fieldSpec.item)
const items = ref<unknown[]>([])
const editing = ref(false)
const busy = ref(false)
const error = ref<string | null>(null)

watch(
  () => props.modelValue,
  (value) => {
    if (!editing.value) items.value = Array.isArray(value) ? [...value] : []
  },
  { immediate: true },
)

const lockedByOther = computed(() => {
  const lock = locks.holderOf(props.dataPath)
  return Boolean(lock && lock.holder.id !== undefined)
})

async function startEdit(): Promise<void> {
  if (editing.value || lockedByOther.value) return
  busy.value = true
  error.value = null
  try {
    await syncClient.lock(props.entity.id, props.dataPath)
    items.value = Array.isArray(props.modelValue) ? [...props.modelValue] : []
    editing.value = true
  } catch (err) {
    error.value = err instanceof Error ? err.message : '无法获取编辑锁'
  } finally {
    busy.value = false
  }
}

async function save(): Promise<void> {
  if (!editing.value) return
  busy.value = true
  error.value = null
  try {
    await syncClient.patch(props.entity.id, props.dataPath, items.value)
    editing.value = false
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    busy.value = false
  }
}

async function cancel(): Promise<void> {
  if (editing.value) {
    await syncClient.unlock(props.entity.id, props.dataPath).catch(() => undefined)
  }
  items.value = Array.isArray(props.modelValue) ? [...props.modelValue] : []
  editing.value = false
}

function addItem(): void {
  if (!itemSpec.value) return
  items.value = [...items.value, defaultValueFor(itemSpec.value)]
}

function removeItem(index: number): void {
  items.value = items.value.filter((_, itemIndex) => itemIndex !== index)
}

function updateItem(index: number, value: unknown): void {
  const next = [...items.value]
  next[index] = value
  items.value = next
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
  <div class="array-field">
    <div class="array-field__header">
      <span class="array-field__label">数组</span>
      <LockHint v-if="locks.holderOf(dataPath)" :entity-id="entity.id" :data-path="dataPath" />
      <span class="array-field__spacer" />
      <button v-if="!editing" class="btn btn--small btn--tonal" type="button" :disabled="lockedByOther || busy" @click="startEdit">
        {{ lockedByOther ? '已锁定' : '编辑' }}
      </button>
      <template v-else>
        <button class="btn btn--small btn--primary" type="button" :disabled="busy" @click="save">保存</button>
        <button class="btn btn--small btn--text" type="button" :disabled="busy" @click="cancel">取消</button>
      </template>
    </div>

    <p v-if="!itemSpec" class="error-text">数组字段缺少 item 定义</p>

    <div v-else class="array-field__items">
      <div v-for="(item, index) in items" :key="index" class="array-field__item">
        <template v-if="itemSpec.type === 'string'">
          <TextField
            :model-value="String(item ?? '')"
            :disabled="!editing || busy"
            @update:model-value="(value) => updateItem(index, value)"
          />
        </template>
        <template v-else-if="itemSpec.type === 'number'">
          <TextField
            :model-value="String(item ?? 0)"
            type="number"
            :disabled="!editing || busy"
            @update:model-value="(value) => updateItem(index, Number(value))"
          />
        </template>
        <label v-else-if="itemSpec.type === 'bool'" class="array-field__bool">
          <input
            type="checkbox"
            :checked="Boolean(item)"
            :disabled="!editing || busy"
            @change="(event) => updateItem(index, (event.target as HTMLInputElement).checked)"
          />
          <span>{{ index }}</span>
        </label>
        <span v-else class="muted">暂不支持该数组元素类型</span>

        <button
          v-if="editing"
          class="btn btn--text btn--small"
          type="button"
          @click="removeItem(index)"
        >
          删除
        </button>
      </div>

      <button v-if="editing" class="btn btn--small btn--tonal" type="button" @click="addItem">
        添加一项
      </button>
    </div>

    <p v-if="error" class="error-text" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.array-field {
  display: grid;
  gap: 6px;
  padding: 8px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
}

.array-field__header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.array-field__label {
  font-weight: 600;
  font-size: 0.85rem;
}

.array-field__spacer {
  flex: 1;
}

.array-field__items {
  display: grid;
  gap: 6px;
}

.array-field__item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.array-field__bool {
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>