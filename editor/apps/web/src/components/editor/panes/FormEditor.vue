<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { EntityRecord } from '@ellia/puzzle-schema'

import { syncClient } from '../../../client/ws'
import { useAuthStore } from '../../../stores/auth'
import { useLocksStore } from '../../../stores/locks'
import { usePresenceStore } from '../../../stores/presence'
import LockHint from '../../presence/LockHint.vue'
import UserBadge from '../../presence/UserBadge.vue'
import { FORM_SPECS } from './form/formSpecs'
import FormField from './form/FormField.vue'

const props = defineProps<{
  entity: EntityRecord
}>()

const auth = useAuthStore()
const locks = useLocksStore()
const presence = usePresenceStore()

const spec = computed(() => FORM_SPECS[props.entity.kind] ?? null)
const specEntries = computed(() => Object.entries(spec.value ?? {}))
const stateRecord = computed(() => props.entity.state as unknown as Record<string, unknown>)

function fieldDataPath(key: string): string {
  return `${props.entity.id}@state:/${key}`
}

function shouldRenderField(key: string): boolean {
  const fieldSpec = spec.value?.[key]
  if (!fieldSpec) return false
  if (fieldSpec.hidden) return false
  // optional 字段未设置时也渲染，显示“未设置”并提供设置入口
  return true
}

// ---------- Fallback JSON editor ----------
const rootPath = computed(() => `${props.entity.id}@state:`)
const draft = ref(JSON.stringify(props.entity.state, null, 2))
const editing = ref(false)
const busy = ref(false)
const message = ref<string | null>(null)

watch(
  () => props.entity.state,
  () => {
    if (!editing.value) {
      draft.value = JSON.stringify(props.entity.state, null, 2)
    }
  },
  { deep: true },
)

const lockedByOther = computed(() => {
  const lock = locks.holderOf(rootPath.value)
  return Boolean(lock && lock.holder.id !== auth.user?.id)
})

const rootPresence = computed(() => presence.userAtPath(props.entity.id, rootPath.value))
const stateKeys = computed(() => Object.keys(stateRecord.value))

function fieldPath(key: string): string {
  return `${props.entity.id}@state:/${key}`
}

function fieldUsers(key: string) {
  return presence.userAtPath(props.entity.id, fieldPath(key))
}

function fieldLocked(key: string): boolean {
  return locks.isLocked(props.entity.id, fieldPath(key))
}

async function startEditing(): Promise<void> {
  message.value = null
  if (lockedByOther.value) return
  busy.value = true
  try {
    await syncClient.lock(props.entity.id, rootPath.value)
    editing.value = true
  } catch (error) {
    message.value = error instanceof Error ? error.message : '无法获取编辑锁'
  } finally {
    busy.value = false
  }
}

async function save(): Promise<void> {
  if (!editing.value) return
  message.value = null
  let parsed: unknown
  try {
    parsed = JSON.parse(draft.value)
  } catch {
    message.value = 'JSON 格式错误'
    return
  }
  busy.value = true
  try {
    await syncClient.patch(props.entity.id, rootPath.value, parsed)
    editing.value = false
  } catch (error) {
    message.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    busy.value = false
  }
}

function cancel(): void {
  if (editing.value) {
    syncClient.unlock(props.entity.id, rootPath.value).catch(() => undefined)
  }
  editing.value = false
  draft.value = JSON.stringify(props.entity.state, null, 2)
}

function onTextareaFocus(): void {
  syncClient.focus(props.entity.id, rootPath.value)
}

function onTextareaBlur(): void {
  syncClient.focus(props.entity.id)
}
</script>

<template>
  <div class="form-editor">

    <template v-if="spec">
      <div class="form-editor__structured">
        <template v-for="[key, fieldSpec] in specEntries" :key="key">
          <FormField
            v-if="shouldRenderField(key)"
            :entity="entity"
            :field-name="key"
            :field-spec="fieldSpec"
            :data-path="fieldDataPath(key)"
            :model-value="stateRecord[key]"
          />
        </template>
      </div>
    </template>

    <template v-else>
      <div v-if="lockedByOther" class="form-editor__banner">
        <LockHint :entity-id="entity.id" :data-path="rootPath" />
      </div>

      <div v-if="rootPresence.length > 0" class="form-editor__presence">
        <UserBadge v-for="user in rootPresence" :key="user.id" :user="user" />
        <span class="muted">正在查看此实体</span>
      </div>

      <div class="form-editor__fields">
        <div v-for="key in stateKeys" :key="key" class="form-editor__field-row">
          <code>{{ key }}</code>
          <span v-if="fieldLocked(key)" class="field-lock-icon" title="该字段已被锁定">🔒</span>
          <span v-if="fieldUsers(key).length > 0" class="form-editor__field-users">
            <UserBadge v-for="user in fieldUsers(key)" :key="user.id" :user="user" />
          </span>
        </div>
      </div>

      <textarea
        class="form-editor__json"
        v-model="draft"
        :readonly="!editing || lockedByOther || busy"
        :disabled="lockedByOther || busy"
        spellcheck="false"
        @focus="onTextareaFocus"
        @blur="onTextareaBlur"
      />

      <p v-if="message" class="error-text" role="alert">{{ message }}</p>

      <div class="form-editor__actions">
        <button v-if="!editing" class="btn btn--tonal" type="button" :disabled="busy || lockedByOther" @click="startEditing">
          {{ lockedByOther ? '已被锁定' : '编辑 JSON' }}
        </button>
        <template v-else>
          <button class="btn btn--primary" type="button" :disabled="busy" @click="save">保存</button>
          <button class="btn btn--text" type="button" :disabled="busy" @click="cancel">取消</button>
        </template>
      </div>
    </template>
  </div>
</template>

<style scoped>
.form-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  padding: 12px;
  box-sizing: border-box;
  overflow-y: auto;
}


.form-editor__structured {
  display: grid;
  gap: 10px;
  align-content: start;
}

.form-editor__banner {
  display: flex;
}

.form-editor__presence {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 28px;
}

.form-editor__fields {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 120px;
  overflow-y: auto;
  padding: 4px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
}

.form-editor__field-row {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.form-editor__field-users {
  display: inline-flex;
  gap: 2px;
}

.field-lock-icon {
  font-size: 0.8rem;
}

.form-editor__json {
  flex: 1;
  min-height: 0;
  resize: none;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.85rem;
  line-height: 1.4;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  padding: 8px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.form-editor__json:disabled {
  opacity: 0.7;
}

.form-editor__actions {
  display: flex;
  gap: 8px;
}
</style>