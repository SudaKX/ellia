<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import {
  ENTITY_KINDS,
  isValidGroup,
  uiKindFor,
  type EntityKind,
  type EntityState,
} from '@ellia/puzzle-schema'

import { syncClient } from '../../../client/ws'
import { useEntitiesStore } from '../../../stores/entities'
import DropdownSelect from '../../ui/DropdownSelect.vue'
import TextField from '../../ui/TextField.vue'
import { CREATE_TEMPLATES } from './createTemplates'

const CUSTOM_GROUP = '__custom__'

const entitiesStore = useEntitiesStore()

const selectedKind = ref<EntityKind>('hint')
const idPart = ref('')
const stateJson = ref('')
const busy = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)
let successTimer: ReturnType<typeof setTimeout> | null = null

const template = computed(() => CREATE_TEMPLATES[selectedKind.value])
const isFixedId = computed(() => template.value.fixed.enable)
const namespace = computed(() => template.value.namespace)
const uiKind = computed(() => uiKindFor(selectedKind.value))
const fullResourceId = computed(() => `${namespace.value}:${idPart.value.trim()}`)

const existingGroups = computed(() =>
  [...new Set(entitiesStore.entityList.map((entity) => entity.group))].sort(),
)

const groupChoice = ref<string>(
  existingGroups.value.includes('main') ? 'main' : CUSTOM_GROUP,
)
const customGroup = ref('main')

const isCustomGroup = computed(() => groupChoice.value === CUSTOM_GROUP)
const effectiveGroup = computed(() =>
  isCustomGroup.value ? customGroup.value.trim() : groupChoice.value,
)

const groupOptions = computed(() => [
  ...existingGroups.value.map((group) => ({ label: group, value: group })),
  { label: '新增分组...', value: CUSTOM_GROUP },
])

watch(groupChoice, (value) => {
  if (value !== CUSTOM_GROUP) customGroup.value = value
})

function resetForKind(kind: EntityKind): void {
  const nextTemplate = CREATE_TEMPLATES[kind]
  stateJson.value = JSON.stringify(nextTemplate.default, null, 2)
  idPart.value = nextTemplate.fixed.enable ? nextTemplate.fixed.value : ''
}

watch(selectedKind, (kind) => {
  resetForKind(kind)
})

watch(idPart, (value) => {
  const currentTemplate = template.value
  if (!currentTemplate.inject_id.enable) return
  try {
    const current = JSON.parse(stateJson.value) as Record<string, unknown>
    if (typeof current !== 'object' || current === null || Array.isArray(current)) return
    stateJson.value = JSON.stringify(
      { ...current, [currentTemplate.inject_id.field]: value.trim() },
      null,
      2,
    )
  } catch {
    // 用户正在编辑非 JSON 内容时，不打断输入
  }
})

resetForKind(selectedKind.value)

onBeforeUnmount(() => {
  if (successTimer) clearTimeout(successTimer)
})

async function createEntity(): Promise<void> {
  error.value = null
  success.value = null

  if (!idPart.value.trim()) {
    error.value = '资源标识符的 id 部分不能为空'
    return
  }

  if (!effectiveGroup.value) {
    error.value = '分组不能为空'
    return
  }

  if (!isValidGroup(effectiveGroup.value)) {
    error.value = '分组必须是合法的 Python 模块名（单段，小写字母/数字/下划线，且不能以数字开头）'
    return
  }

  let state: Record<string, unknown>
  try {
    state = JSON.parse(stateJson.value) as Record<string, unknown>
  } catch {
    error.value = 'state 必须是合法 JSON'
    return
  }

  if (typeof state !== 'object' || state === null || Array.isArray(state)) {
    error.value = 'state 必须是一个 JSON 对象'
    return
  }

  if (template.value.inject_id.enable) {
    state = { ...state, [template.value.inject_id.field]: idPart.value.trim() }
  }

  busy.value = true
  try {
    await syncClient.create({
      group: effectiveGroup.value,
      kind: selectedKind.value,
      ui_kind: uiKind.value,
      resource_id: fullResourceId.value,
      state: state as unknown as EntityState,
    })
    success.value = `已创建 ${fullResourceId.value}`
    if (successTimer) clearTimeout(successTimer)
    successTimer = setTimeout(() => {
      success.value = null
    }, 3000)
    if (!template.value.fixed.enable) idPart.value = ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : '创建失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="create-entity-panel">
    <header class="create-entity-panel__header">
      <h3>创建实体</h3>
    </header>

    <form class="create-entity-panel__form" @submit.prevent="createEntity">
      <label class="create-entity-field">
        <span>类别</span>
        <DropdownSelect
          :options="ENTITY_KINDS.map((kind) => ({ label: kind, value: kind }))"
          :model-value="selectedKind"
          @update:model-value="(value) => selectedKind = value as EntityKind"
        />
        <div v-if="template.comment.description" class="create-entity-field__surface">
          {{ template.comment.description }}
        </div>
      </label>

      <label class="create-entity-field">
        <span>分组</span>
        <DropdownSelect
          :options="groupOptions"
          :model-value="groupChoice"
          placeholder="选择分组"
          @update:model-value="(value) => groupChoice = String(value)"
        />
      </label>

      <div class="create-entity-field">
        <TextField
          v-model="customGroup"
          placeholder="输入自定义分组"
          :disabled="!isCustomGroup"
        />
      </div>

      <label class="create-entity-field">
        <span>资源标识符</span>
        <div class="resource-id-input">
          <span class="resource-id-input__prefix">{{ namespace }}:</span>
          <TextField
            v-model="idPart"
            placeholder="输入 id 部分"
            :disabled="isFixedId"
          />
        </div>
        <div class="create-entity-field__surface">
          {{ template.comment.format }}
        </div>
      </label>

      <label class="create-entity-field">
        <span>state（JSON）</span>
        <textarea v-model="stateJson" rows="12" spellcheck="false" />
      </label>

      <p v-if="error" class="error-text" role="alert">{{ error }}</p>
      <p v-else-if="success" class="success-text" role="status">{{ success }}</p>

      <button class="btn btn--primary" type="submit" :disabled="busy">
        {{ busy ? '创建中…' : '创建实体' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.create-entity-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 10px;
  gap: 10px;
  overflow-y: auto;
}

.create-entity-panel__header h3 {
  margin: 0;
  font-size: 1rem;
}

.create-entity-panel__form {
  display: grid;
  gap: 10px;
}

.create-entity-field {
  display: grid;
  gap: 4px;
  font-size: 0.85rem;
}

.create-entity-field__surface {
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font-size: 0.75rem;
  line-height: 1.4;
}

.create-entity-field textarea {
  min-height: 160px;
  resize: vertical;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.8rem;
  padding: 6px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.resource-id-input {
  display: flex;
  align-items: center;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  overflow: hidden;
}

.resource-id-input:focus-within {
  outline: 2px solid var(--md-sys-color-primary, #6750a4);
  outline-offset: 1px;
}

.resource-id-input__prefix {
  flex: none;
  padding: 0 0 0 8px;
  font-size: 0.85rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.resource-id-input :deep(.text-field) {
  border: none;
  border-radius: 0;
  background: transparent;
  min-height: 30px;
}

.resource-id-input :deep(.text-field:focus-visible) {
  outline: none;
}

.success-text {
  color: var(--md-sys-color-primary, #6750a4);
  font-size: 0.85rem;
}
</style>