<script setup lang="ts">
import { computed, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'

import { EditorView, basicSetup } from 'codemirror'
import { Compartment } from '@codemirror/state'
import { keymap } from '@codemirror/view'
import { indentWithTab } from '@codemirror/commands'
import { python } from '@codemirror/lang-python'
import type { EntityRecord } from '@ellia/puzzle-schema'

import { syncClient } from '../../../client/ws'
import { useAuthStore } from '../../../stores/auth'
import { useLocksStore } from '../../../stores/locks'
import { useStyleStore } from '../../../stores/style'
import LockOverlay from '../../presence/LockOverlay.vue'

const props = withDefaults(
  defineProps<{
    entity: EntityRecord
    dataPath: string
    modelValue: string
    patchValue?: (value: string) => unknown
  }>(),
  {
    patchValue: (value: string) => value,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const auth = useAuthStore()
const locks = useLocksStore()
const styleStore = useStyleStore()

const container = ref<HTMLElement | null>(null)
const draft = ref(props.modelValue)
const editing = ref(false)
const focused = ref(false)
const busy = ref(false)
const message = ref<string | null>(null)
const copied = ref(false)
let copyTimer: ReturnType<typeof setTimeout> | null = null

const editableCompartment = new Compartment()
const themeCompartment = new Compartment()
const highlightCompartment = new Compartment()
let view: EditorView | null = null

const lockInfo = computed(() => locks.holderOf(props.dataPath))
const lockedByOther = computed(
  () => Boolean(lockInfo.value && lockInfo.value.holder.id !== auth.user?.id),
)

function createView(): void {
  if (!container.value) return
  view = new EditorView({
    doc: props.modelValue,
    extensions: [
      basicSetup,
      python(),
      themeCompartment.of(styleStore.editorTheme),
      highlightCompartment.of(styleStore.pythonHighlight),
      keymap.of([indentWithTab]),
      editableCompartment.of(EditorView.editable.of(false)),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          const value = update.state.doc.toString()
          draft.value = value
          emit('update:modelValue', value)
        }
      }),
      EditorView.domEventHandlers({
        focus: () => {
          focused.value = true
          syncClient.focus(props.entity.id, props.dataPath)
        },
        blur: () => {
          focused.value = false
        },
      }),
    ],
    parent: container.value,
  })
}

async function copyContent(): Promise<void> {
  const text = view ? view.state.doc.toString() : draft.value
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => {
      copied.value = false
      copyTimer = null
    }, 1500)
  } catch {
    message.value = '复制失败'
  }
}

function setEditable(editable: boolean): void {
  if (!view) return
  view.dispatch({
    effects: editableCompartment.reconfigure(EditorView.editable.of(editable)),
  })
}

async function startEditing(): Promise<void> {
  if (editing.value || lockedByOther.value) return
  busy.value = true
  message.value = null
  try {
    await syncClient.lock(props.entity.id, props.dataPath)
    editing.value = true
    setEditable(true)
  } catch (error) {
    message.value = error instanceof Error ? error.message : '无法获取编辑锁'
  } finally {
    busy.value = false
  }
}

async function finishEditing(): Promise<void> {
  if (!editing.value) return
  busy.value = true
  message.value = null
  let succeeded = false
  try {
    await syncClient.patch(props.entity.id, props.dataPath, props.patchValue(draft.value))
    succeeded = true
  } catch (error) {
    message.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    await stopEditing(!succeeded)
    busy.value = false
  }
}

async function cancelEditing(): Promise<void> {
  await stopEditing(true)
}

async function stopEditing(unlock: boolean): Promise<void> {
  if (unlock && editing.value) {
    await syncClient.unlock(props.entity.id, props.dataPath).catch(() => undefined)
  }
  editing.value = false
  setEditable(false)
}

onMounted(() => {
  styleStore.init()
  createView()
})

watch(
  () => styleStore.editorTheme,
  (theme) => {
    if (!view) return
    view.dispatch({ effects: themeCompartment.reconfigure(theme) })
  },
)

watch(
  () => styleStore.pythonHighlight,
  (highlight) => {
    if (!view) return
    view.dispatch({ effects: highlightCompartment.reconfigure(highlight) })
  },
)

watch(
  () => props.modelValue,
  (value) => {
    if (!editing.value && view) {
      const current = view.state.doc.toString()
      if (current !== value) {
        view.dispatch({ changes: { from: 0, to: current.length, insert: value } })
        draft.value = value
      }
    }
  },
)

watch(lockedByOther, (value) => {
  if (value && editing.value) {
    editing.value = false
    setEditable(false)
  }
})

onBeforeUnmount(() => {
  if (editing.value) {
    syncClient.unlock(props.entity.id, props.dataPath).catch(() => undefined)
  }
  view?.destroy()
  view = null
})

onDeactivated(() => {
  void stopEditing(true)
})
</script>

<template>
  <div class="code-editor">
    <p v-if="message" class="error-text" role="alert">{{ message }}</p>

    <div
      class="code-editor__frame"
      :class="{ 'code-editor__frame--editing': editing }"
    >
      <div
        ref="container"
        class="code-editor__container"
      />
      <LockOverlay v-if="lockedByOther && lockInfo" :username="lockInfo.holder.username" />
      <div class="code-editor__copy-zone">
        <button
          class="code-editor__copy btn btn--text btn--small"
          type="button"
          @click="copyContent"
        >
          {{ copied ? '已复制' : '复制' }}
        </button>
      </div>
      <div class="code-editor__actions">
        <button
          v-if="!editing"
          class="code-editor__fab btn btn--primary"
          type="button"
          :disabled="busy || lockedByOther"
          @click="startEditing"
        >
          {{ lockedByOther ? '已被锁定' : '编辑' }}
        </button>
        <template v-else>
          <button class="code-editor__fab btn btn--primary" type="button" :disabled="busy" @click="finishEditing">
            完成
          </button>
          <button class="code-editor__fab btn btn--text" type="button" :disabled="busy" @click="cancelEditing">
            取消
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.code-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 100%;
  padding: 12px;
  box-sizing: border-box;
}

.code-editor__frame {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container, #f3edf7);
}

.code-editor__frame--editing {
  outline: 2px solid var(--md-sys-color-primary, #6750a4);
  outline-offset: 1px;
}

.code-editor__container {
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: auto;
}

.code-editor__copy-zone {
  position: absolute;
  top: 0;
  right: 0;
  z-index: 12;
  width: 72px;
  height: 72px;
  padding: 8px;
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  pointer-events: auto;
}

.code-editor__copy {
  min-width: 48px;
  box-sizing: border-box;
  white-space: nowrap;
  text-align: center;
  border-radius: 999px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  box-shadow: 0 2px 8px rgb(0 0 0 / 0.15);
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 0.15s ease,
    background-color 0.15s ease;
}

.code-editor__copy-zone:hover .code-editor__copy,
.code-editor__copy:focus-visible {
  opacity: 1;
  pointer-events: auto;
}

.code-editor__copy:hover {
  background: var(--md-sys-color-surface-container-highest, #e6e0e9);
}

.code-editor__copy:active {
  background: var(--md-sys-color-surface-container-highest, #e6e0e9);
}

.code-editor__actions {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 11;
  display: flex;
  gap: 8px;
}

.code-editor__fab {
  border-radius: 999px;
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.2);
}

.code-editor__container :deep(.cm-editor) {
  height: 100%;
}

.code-editor__container :deep(.cm-content),
.code-editor__container :deep(.cm-gutters) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
</style>
