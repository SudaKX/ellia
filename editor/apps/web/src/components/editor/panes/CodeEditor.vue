<script setup lang="ts">
import { computed, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'

import { EditorView, basicSetup } from 'codemirror'
import { Compartment } from '@codemirror/state'
import { python } from '@codemirror/lang-python'
import type { EntityRecord } from '@ellia/puzzle-schema'

import { syncClient } from '../../../client/ws'
import { useLocksStore } from '../../../stores/locks'
import LockHint from '../../presence/LockHint.vue'

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

const locks = useLocksStore()

const container = ref<HTMLElement | null>(null)
const editing = ref(false)
const focused = ref(false)
const busy = ref(false)
const message = ref<string | null>(null)

const editableCompartment = new Compartment()
let view: EditorView | null = null
let pendingTimer: ReturnType<typeof setTimeout> | null = null

const lockedByOther = computed(() => {
  const lock = locks.holderOf(props.dataPath)
  return Boolean(lock && lock.holder.id !== undefined)
})

function createView(): void {
  if (!container.value) return
  view = new EditorView({
    doc: props.modelValue,
    extensions: [
      basicSetup,
      python(),
      editableCompartment.of(EditorView.editable.of(false)),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          const value = update.state.doc.toString()
          emit('update:modelValue', value)
          schedulePatch()
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
    focused.value = true
    setEditable(true)
  } catch (error) {
    message.value = error instanceof Error ? error.message : '无法获取编辑锁'
  } finally {
    busy.value = false
  }
}

async function flushPatch(): Promise<void> {
  if (!editing.value) return
  try {
    await syncClient.patch(props.entity.id, props.dataPath, props.patchValue(props.modelValue))
    if (editing.value) {
      await syncClient.lock(props.entity.id, props.dataPath)
    }
  } catch (error) {
    message.value = error instanceof Error ? error.message : '保存失败'
    await stopEditing(true)
  }
}

function schedulePatch(): void {
  if (pendingTimer) clearTimeout(pendingTimer)
  pendingTimer = setTimeout(() => {
    pendingTimer = null
    void flushPatch()
  }, 500)
}

async function finishEditing(): Promise<void> {
  if (pendingTimer) {
    clearTimeout(pendingTimer)
    pendingTimer = null
  }
  if (editing.value) {
    await flushPatch()
  }
  await stopEditing(true)
}

async function stopEditing(unlock: boolean): Promise<void> {
  if (pendingTimer) {
    clearTimeout(pendingTimer)
    pendingTimer = null
  }
  if (unlock && editing.value) {
    await syncClient.unlock(props.entity.id, props.dataPath).catch(() => undefined)
  }
  editing.value = false
  focused.value = false
  setEditable(false)
}

onMounted(() => {
  createView()
})

watch(
  () => props.modelValue,
  (value) => {
    if (!editing.value && view) {
      const current = view.state.doc.toString()
      if (current !== value) {
        view.dispatch({ changes: { from: 0, to: current.length, insert: value } })
      }
    }
  },
)

onBeforeUnmount(() => {
  if (pendingTimer) clearTimeout(pendingTimer)
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
    <header class="code-editor__header">
      <h2>{{ entity.resource_id }}</h2>
      <span class="muted">{{ entity.kind }} · v{{ entity.version }} · r{{ entity.revision }}</span>
      <span class="code-editor__spacer" />
      <button v-if="!editing" class="btn btn--tonal" type="button" :disabled="busy || lockedByOther" @click="startEditing">
        {{ lockedByOther ? '已被锁定' : '编辑' }}
      </button>
      <template v-else>
        <button class="btn btn--primary" type="button" :disabled="busy" @click="finishEditing">完成</button>
        <button class="btn btn--text" type="button" :disabled="busy" @click="stopEditing(true)">取消</button>
      </template>
    </header>

    <div v-if="lockedByOther" class="code-editor__lock">
      <LockHint :entity-id="entity.id" :data-path="dataPath" />
    </div>

    <p v-if="message" class="error-text" role="alert">{{ message }}</p>

    <div
      ref="container"
      class="code-editor__container"
      :class="{ 'code-editor__container--editing': editing }"
    />
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

.code-editor__header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.code-editor__header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.code-editor__spacer {
  flex: 1;
}

.code-editor__container {
  flex: 1;
  min-height: 0;
  overflow: auto;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container, #f3edf7);
}

.code-editor__container--editing {
  outline: 2px solid var(--md-sys-color-primary, #6750a4);
}

.code-editor__container :deep(.cm-editor) {
  height: 100%;
}
</style>