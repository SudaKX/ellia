<script setup lang="ts">
import { computed, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'

import { EditorView, basicSetup } from 'codemirror'
import { Compartment } from '@codemirror/state'
import { keymap } from '@codemirror/view'
import { indentWithTab } from '@codemirror/commands'
import { json } from '@codemirror/lang-json'
import type { EntityRecord } from '@ellia/puzzle-schema'

import { syncClient } from '../../../client/ws'
import { useAuthStore } from '../../../stores/auth'
import { useLocksStore } from '../../../stores/locks'
import { useStyleStore } from '../../../stores/style'
import LockOverlay from '../../presence/LockOverlay.vue'

const props = withDefaults(
  defineProps<{
    entity: EntityRecord
    embedded?: boolean
  }>(),
  { embedded: false },
)

const auth = useAuthStore()
const locks = useLocksStore()
const styleStore = useStyleStore()

locks.ensureSubscriptions()

const rootPath = computed(() => `${props.entity.id}@state:`)
const editing = ref(false)
const busy = ref(false)
const message = ref<string | null>(null)

const container = ref<HTMLElement | null>(null)
const editableCompartment = new Compartment()
const themeCompartment = new Compartment()
const highlightCompartment = new Compartment()
let view: EditorView | null = null

const otherStateLocks = computed(() => {
  const prefix = `${props.entity.id}@state`
  return locks.lockList.filter(
    (lock) =>
      lock.entityId === props.entity.id &&
      lock.dataPath.startsWith(prefix) &&
      lock.holder.id !== auth.user?.id,
  )
})

const lockedByOther = computed(() => otherStateLocks.value.length > 0)

function createView(): void {
  if (!container.value) return
  view = new EditorView({
    doc: JSON.stringify(props.entity.state, null, 2),
    extensions: [
      basicSetup,
      json(),
      themeCompartment.of(styleStore.editorTheme),
      highlightCompartment.of(styleStore.jsonHighlight),
      keymap.of([indentWithTab]),
      editableCompartment.of(EditorView.editable.of(false)),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          message.value = null
        }
      }),
      EditorView.domEventHandlers({
        focus: () => {
          syncClient.focus(props.entity.id, rootPath.value)
        },
        blur: () => {
          syncClient.focus(props.entity.id)
        },
      }),
    ],
    parent: container.value,
  })
}

function setEditable(editable: boolean): void {
  if (!view) return
  view.dispatch({
    effects: editableCompartment.reconfigure(EditorView.editable.of(editable)),
  })
}

function syncFromEntity(): void {
  if (!view || editing.value) return
  const value = JSON.stringify(props.entity.state, null, 2)
  const current = view.state.doc.toString()
  if (current !== value) {
    view.dispatch({ changes: { from: 0, to: current.length, insert: value } })
  }
}

function resetToEntityState(): void {
  if (!view) return
  const value = JSON.stringify(props.entity.state, null, 2)
  const current = view.state.doc.toString()
  if (current !== value) {
    view.dispatch({ changes: { from: 0, to: current.length, insert: value } })
  }
}

async function startEditing(): Promise<void> {
  if (editing.value || lockedByOther.value) return
  busy.value = true
  message.value = null
  try {
    await syncClient.lock(props.entity.id, rootPath.value)
    editing.value = true
    setEditable(true)
  } catch (error) {
    message.value = error instanceof Error ? error.message : '无法获取编辑锁'
  } finally {
    busy.value = false
  }
}

async function stopEditing(unlock: boolean, reset = false): Promise<void> {
  if (unlock && editing.value) {
    await syncClient.unlock(props.entity.id, rootPath.value).catch(() => undefined)
  }
  editing.value = false
  setEditable(false)
  if (reset) {
    resetToEntityState()
  }
}

async function save(): Promise<void> {
  if (!editing.value) return
  message.value = null
  const value = view ? view.state.doc.toString() : ''
  let parsed: unknown
  try {
    parsed = JSON.parse(value)
  } catch {
    message.value = 'JSON 格式错误'
    return
  }
  busy.value = true
  let succeeded = false
  try {
    await syncClient.patch(props.entity.id, rootPath.value, parsed)
    succeeded = true
  } catch (error) {
    message.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    await stopEditing(!succeeded, !succeeded)
    busy.value = false
  }
}

function cancel(): void {
  void stopEditing(true, true)
}

watch(
  () => props.entity.state,
  () => syncFromEntity(),
  { deep: true },
)

watch(
  () => styleStore.editorTheme,
  (theme) => {
    if (!view) return
    view.dispatch({ effects: themeCompartment.reconfigure(theme) })
  },
)

watch(
  () => styleStore.jsonHighlight,
  (highlight) => {
    if (!view) return
    view.dispatch({ effects: highlightCompartment.reconfigure(highlight) })
  },
)

watch(lockedByOther, (value) => {
  if (value && editing.value) {
    void stopEditing(true, true)
  }
})

onMounted(() => {
  styleStore.init()
  createView()
})

onBeforeUnmount(() => {
  if (editing.value) {
    syncClient.unlock(props.entity.id, rootPath.value).catch(() => undefined)
  }
  view?.destroy()
  view = null
})

onDeactivated(() => {
  void stopEditing(true, true)
})
</script>

<template>
  <div class="fallback-editor" :class="{ 'fallback-editor--embedded': embedded }">
    <div
      class="fallback-editor__frame"
      :class="{ 'fallback-editor__frame--editing': editing }"
    >
      <div ref="container" class="fallback-editor__container" />
      <LockOverlay
        v-if="lockedByOther && otherStateLocks[0]"
        :username="otherStateLocks[0].holder.username"
      />
      <div class="fallback-editor__actions">
        <button
          v-if="!editing"
          class="fallback-editor__fab btn btn--primary"
          type="button"
          :disabled="busy || lockedByOther"
          @click="startEditing"
        >
          {{ lockedByOther ? '已被锁定' : '编辑' }}
        </button>
        <template v-else>
          <button
            class="fallback-editor__fab btn btn--primary"
            type="button"
            :disabled="busy"
            @click="save"
          >
            确认
          </button>
          <button
            class="fallback-editor__fab btn btn--text"
            type="button"
            :disabled="busy"
            @click="cancel"
          >
            取消
          </button>
        </template>
      </div>
    </div>

    <p v-if="message" class="error-text" role="alert">{{ message }}</p>
  </div>
</template>

<style scoped>
.fallback-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 100%;
  min-height: 0;
  padding: 12px;
  box-sizing: border-box;
  overflow: hidden;
}

.fallback-editor--embedded {
  padding: 0;
}

.fallback-editor__frame {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container, #f3edf7);
}

.fallback-editor__frame--editing {
  outline: 2px solid var(--md-sys-color-primary, #6750a4);
  outline-offset: 1px;
}

.fallback-editor__container {
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: auto;
}

.fallback-editor__container :deep(.cm-editor) {
  height: 100%;
}

.fallback-editor__container :deep(.cm-content),
.fallback-editor__container :deep(.cm-gutters) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.fallback-editor__actions {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 11;
  display: flex;
  gap: 8px;
}

.fallback-editor__fab {
  border-radius: 999px;
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.2);
}
</style>
