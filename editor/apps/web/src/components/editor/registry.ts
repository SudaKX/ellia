import type { Component } from 'vue'

import {
  uiKindFor,
  type EntityKind,
  type EntityRecord,
  type UiKind,
} from '@ellia/puzzle-schema'

import AssetEditor from './panes/AssetEditor.vue'
import CodeEditor from './panes/CodeEditor.vue'
import FileTreeEditor from './panes/FileTreeEditor.vue'
import FileTreeNodeEditor from './panes/FileTreeNodeEditor.vue'
import FormEditor from './panes/FormEditor.vue'
import ProgressDagEditor from './panes/ProgressDagEditor.vue'
import ProgressNodeEditor from './panes/ProgressNodeEditor.vue'
import ScriptEditor from './panes/ScriptEditor.vue'

const kindRegistry = new Map<EntityKind, Component>()
const uiKindRegistry = new Map<UiKind, Component>()

registerKindEditor('progress-node', ProgressNodeEditor)
registerKindEditor('file-tree-node', FileTreeNodeEditor)
registerKindEditor('file-tree', FileTreeEditor)
registerKindEditor('progress-dag', ProgressDagEditor)
registerKindEditor('asset', AssetEditor)
registerKindEditor('script', ScriptEditor)
registerKindEditor('python-block', CodeEditor)

registerUiKindEditor('dag-node', ProgressNodeEditor)
registerUiKindEditor('tree-node', FileTreeNodeEditor)
registerUiKindEditor('file-tree', FileTreeEditor)
registerUiKindEditor('progress-dag', ProgressDagEditor)
registerUiKindEditor('asset', AssetEditor)
registerUiKindEditor('script', ScriptEditor)
registerUiKindEditor('code', CodeEditor)
registerUiKindEditor('form', FormEditor)

export function registerKindEditor(kind: EntityKind, component: Component): void {
  kindRegistry.set(kind, component)
}

export function registerUiKindEditor(uiKind: UiKind, component: Component): void {
  uiKindRegistry.set(uiKind, component)
}

export function resolveEditorForEntity(entity: EntityRecord): Component {
  const byKind = kindRegistry.get(entity.kind)
  if (byKind) return byKind
  const byUiKind = uiKindRegistry.get(entity.ui_kind)
  if (byUiKind) return byUiKind
  const defaultUiKind = uiKindFor(entity.kind)
  const byDefault = uiKindRegistry.get(defaultUiKind)
  return byDefault ?? FormEditor
}

export function registeredComponentNames(): string[] {
  return [...kindRegistry.values(), ...uiKindRegistry.values()]
    .map((component) => (component as { name?: string }).name)
    .filter((name): name is string => Boolean(name))
}

export { FormEditor }