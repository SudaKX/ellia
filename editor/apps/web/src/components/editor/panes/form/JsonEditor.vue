<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { EditorView, basicSetup } from 'codemirror'
import { Compartment } from '@codemirror/state'
import { json } from '@codemirror/lang-json'

import { useStyleStore } from '../../../../stores/style'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const styleStore = useStyleStore()

const container = ref<HTMLElement | null>(null)
let view: EditorView | null = null
const themeCompartment = new Compartment()
const highlightCompartment = new Compartment()

function createView(): void {
  if (!container.value) return
  view = new EditorView({
    doc: props.modelValue,
    extensions: [
      basicSetup,
      json(),
      themeCompartment.of(styleStore.editorTheme),
      highlightCompartment.of(styleStore.jsonHighlight),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          emit('update:modelValue', update.state.doc.toString())
        }
      }),
    ],
    parent: container.value,
  })
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
  () => styleStore.jsonHighlight,
  (highlight) => {
    if (!view) return
    view.dispatch({ effects: highlightCompartment.reconfigure(highlight) })
  },
)

watch(
  () => props.modelValue,
  (value) => {
    if (!view) return
    const current = view.state.doc.toString()
    if (current !== value) {
      view.dispatch({ changes: { from: 0, to: current.length, insert: value } })
    }
  },
)

onBeforeUnmount(() => {
  view?.destroy()
  view = null
})
</script>

<template>
  <div ref="container" class="json-editor" />
</template>

<style scoped>
.json-editor {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
  height: 360px;
  max-height: 65vh;
  overflow: hidden;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container, #f3edf7);
}

.json-editor :deep(.cm-editor) {
  width: 100%;
  min-width: 0;
  height: 100%;
  min-height: 360px;
}

.json-editor :deep(.cm-scroller) {
  width: 100%;
  min-width: 0;
  overflow: auto;
}

.json-editor :deep(.cm-content),
.json-editor :deep(.cm-gutters) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
</style>
