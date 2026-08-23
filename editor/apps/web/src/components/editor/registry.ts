import type { Component } from 'vue'

import {
  uiKindFor,
  type EntityKind,
  type EntityRecord,
  type UiKind,
} from '@ellia/puzzle-schema'

import CodeBlockEditor from './panes/CodeBlockEditor.vue'
import FileTreeEditor from './panes/FileTreeEditor.vue'
import FormEditor from './panes/FormEditor.vue'
import DagEditor from './panes/DagEditor.vue'
import ScriptEditor from './panes/ScriptEditor.vue'

const kindRegistry = new Map<EntityKind, Component>()
const uiKindRegistry = new Map<UiKind, Component>()

registerKindEditor('progress-node', FormEditor)
registerKindEditor('file-tree', FileTreeEditor)
registerKindEditor('dag', DagEditor)
registerKindEditor('asset', FormEditor)
registerKindEditor('script', ScriptEditor)
registerKindEditor('code', CodeBlockEditor)

registerUiKindEditor('dag-node', FormEditor)
registerUiKindEditor('file-tree', FileTreeEditor)
registerUiKindEditor('dag', DagEditor)
registerUiKindEditor('asset', FormEditor)
registerUiKindEditor('script', ScriptEditor)
registerUiKindEditor('code', CodeBlockEditor)
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