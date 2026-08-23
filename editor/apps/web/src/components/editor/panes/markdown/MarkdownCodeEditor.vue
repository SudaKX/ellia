<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { EditorView, basicSetup } from 'codemirror'
import { Compartment } from '@codemirror/state'
import { keymap } from '@codemirror/view'
import { indentWithTab } from '@codemirror/commands'
import { markdown } from '@codemirror/lang-markdown'

import { useStyleStore } from '../../../../stores/style'

const props = withDefaults(
  defineProps<{
    modelValue: string
    editable?: boolean
  }>(),
  { editable: true },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const styleStore = useStyleStore()

const container = ref<HTMLElement | null>(null)
const editableCompartment = new Compartment()
const themeCompartment = new Compartment()
const highlightCompartment = new Compartment()
let view: EditorView | null = null

function createView(): void {
  if (!container.value) return
  view = new EditorView({
    doc: props.modelValue,
    extensions: [
      basicSetup,
      markdown(),
      themeCompartment.of(styleStore.editorTheme),
      highlightCompartment.of(styleStore.markdownHighlight),
      keymap.of([indentWithTab]),
      editableCompartment.of(EditorView.editable.of(props.editable)),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          emit('update:modelValue', update.state.doc.toString())
        }
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

watch(
  () => props.editable,
  (editable) => setEditable(editable),
)

watch(
  () => styleStore.editorTheme,
  (theme) => {
    if (!view) return
    view.dispatch({ effects: themeCompartment.reconfigure(theme) })
  },
)

watch(
  () => styleStore.markdownHighlight,
  (highlight) => {
    if (!view) return
    view.dispatch({ effects: highlightCompartment.reconfigure(highlight) })
  },
)

onMounted(() => {
  styleStore.init()
  createView()
})

onBeforeUnmount(() => {
  view?.destroy()
  view = null
})
</script>

<template>
  <div ref="container" class="markdown-code-editor" />
</template>

<style scoped>
.markdown-code-editor {
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.markdown-code-editor :deep(.cm-editor) {
  height: 100%;
}

.markdown-code-editor :deep(.cm-scroller) {
  overflow: auto;
}

.markdown-code-editor :deep(.cm-content),
.markdown-code-editor :deep(.cm-gutters) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
</style>
