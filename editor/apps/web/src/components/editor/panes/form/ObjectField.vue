<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { EntityRecord } from '@ellia/puzzle-schema'

import { syncClient } from '../../../../client/ws'
import { useLocksStore } from '../../../../stores/locks'
import LockHint from '../../../presence/LockHint.vue'
import type { FieldSpec } from './formTypes'
import FormField from './FormField.vue'

const props = defineProps<{
  entity: EntityRecord
  fieldSpec: FieldSpec
  dataPath: string
  modelValue: unknown
}>()

const locks = useLocksStore()

const inner = computed(() => props.fieldSpec.inner ?? {})
const keys = computed(() => Object.keys(inner.value))
const objectValue = computed(() =>
  props.modelValue && typeof props.modelValue === 'object' ? (props.modelValue as Record<string, unknown>) : {},
)

function childPath(key: string): string {
  const [head, rest] = props.dataPath.split('@state:', 2)
  if (rest === undefined) return `${props.dataPath}/${key}`
  return `${head}@state:${rest}/${key}`
}

// 空 inner 时退化为 JSON 对象编辑
const jsonDraft = ref('')
const editing = ref(false)
const busy = ref(false)
const error = ref<string | null>(null)

watch(
  () => props.modelValue,
  (value) => {
    if (!editing.value) jsonDraft.value = JSON.stringify(value ?? {}, null, 2)
  },
  { immediate: true },
)

async function startJsonEdit(): Promise<void> {
  if (editing.value) return
  busy.value = true
  error.value = null
  try {
    await syncClient.lock(props.entity.id, props.dataPath)
    editing.value = true
  } catch (err) {
    error.value = err instanceof Error ? err.message : '无法获取编辑锁'
  } finally {
    busy.value = false
  }
}

async function saveJson(): Promise<void> {
  if (!editing.value) return
  let parsed: unknown
  try {
    parsed = JSON.parse(jsonDraft.value)
  } catch {
    error.value = 'JSON 格式错误'
    return
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    error.value = '必须是 JSON 对象'
    return
  }
  busy.value = true
  error.value = null
  try {
    await syncClient.patch(props.entity.id, props.dataPath, parsed)
    editing.value = false
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="object-field">
    <template v-if="keys.length > 0">
      <div v-for="key in keys" :key="key" class="object-field__child">
        <FormField
          v-if="!inner[key]?.hidden"
          :entity="entity"
          :field-name="key"
          :field-spec="inner[key]!"
          :data-path="childPath(key)"
          :model-value="objectValue[key]"
        />
      </div>
    </template>

    <template v-else>
      <div class="object-field__json">
        <div class="object-field__json-header">
          <span class="muted">对象字段（JSON）</span>
          <LockHint v-if="locks.holderOf(dataPath)" :entity-id="entity.id" :data-path="dataPath" />
        </div>
        <textarea
          v-model="jsonDraft"
          :readonly="!editing"
          :disabled="busy"
          rows="6"
          spellcheck="false"
          @focus="startJsonEdit"
        />
        <div v-if="editing" class="object-field__json-actions">
          <button class="btn btn--small btn--primary" type="button" :disabled="busy" @click="saveJson">保存</button>
        </div>
        <p v-if="error" class="error-text" role="alert">{{ error }}</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.object-field {
  display: grid;
  gap: 6px;
}

.object-field__child {
  display: grid;
}

.object-field__json {
  display: grid;
  gap: 6px;
}

.object-field__json-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.object-field__json textarea {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.8rem;
  padding: 6px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.object-field__json-actions {
  display: flex;
  justify-content: flex-end;
}
</style>