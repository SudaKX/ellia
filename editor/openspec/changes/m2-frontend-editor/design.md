## Context

See `proposal.md` for motivation. The backend M1.2 + M2 layer is complete: projects CRUD, entities/history/files, WS v2 protocol, locks, presence, and file REST exist. The frontend only has auth/admin pages and a placeholder home page. The existing frontend uses Vue 3 + Pinia + vue-router with Material 3 tokens; `@ellia/puzzle-schema` already defines WS v2 message types and entity types.

## Goals / Non-Goals

**Goals:**

- Deliver a working project list and `/projects/:id` editor workspace.
- Establish a durable frontend architecture: one communication layer, one entity store, one editor registry.
- Support multi-tab editing with preserved component state, field locks, and presence display.
- Make the required backend protocol/list extensions small and backward-compatible.

**Non-Goals:**

- Not implementing M3 zip export in this change.
- Not implementing full CRDT/offline editing.
- Not implementing advanced DAG visualization beyond basic editor forms in this first pass.
- Not adding project-level permission isolation; existing global two-role model stays.

## Decisions

### 1. Use a custom resizable split layout instead of a library

Implement `SplitView`/`SplitDivider` with pointer events and CSS variables (`--left-width`, `--right-width`). Initial values are `2fr : 3fr : 2fr`; min widths are enforced (`240px / 480px / 240px`).

Rationale: avoids a dependency; the interaction is simple; widths persist as plain numbers in localStorage.

Alternative considered: `splitpanes` package. Rejected to keep dependency surface low.

### 2. Single Pinia entity store keyed by UUID

Use a Pinia store with `entities: Record<EntityId, EntityRecord>` for the current project, plus `projectId` and `lastSyncAt`. All WS messages update this store:

- `sync` → replace/delete according to server payload
- `created` → upsert
- `update` → apply data path to stored state and bump revision/version
- `rolled_back` → replace state and set revision/version
- `deleted` → delete key

Rationale: one source of truth makes cards, tabs, editors, and tool panels agree automatically.

Alternative considered: per-component local refs. Rejected because broadcasts would need manual fan-out and stale copies are likely.

### 3. Persist only entity store and layout widths

localStorage keys:

- `ellia:entities:<projectId>` — serialized entity record map
- `ellia:layout:<projectId>` — `{ leftWidth, rightWidth }`

Writes are debounced (e.g. 500ms). Parse failures or quota errors degrade silently; server `sync` remains authoritative.

### 4. `SyncClient` with typed subscriptions and promise-capable active functions

Create `src/client/ws/SyncClient.ts`:

- Low-level `send(message)`.
- Typed `on<T>(type, handler)` / `off`; returns an unsubscribe function.
- Active functions: `join`, `create`, `lock`, `unlock`, `patch`, `delete`, `rollback`, `history`, `focus`, `ping`.
- Promise helpers for operations that carry `ref`: `create`, `patch`, `lock`, `unlock`, `delete`, `rollback`, `history` resolve on the matching ack/broadcast and reject on `error` with the same `ref`.

To support promises, extend the protocol (see specs) so `locked`, `unlocked`, `deleted`, and `rolled_back` echo `ref`; `unlock` also accepts `ref`. Unknown refs received by other clients are ignored.

Rationale: components can write `await syncClient.patch(...)` for common actions while stores still subscribe to all broadcasts to stay current.

Alternative considered: fire-and-forget only. It works but makes operation-bar/error UX less ergonomic; the protocol extension is small.

### 5. Editor registry keyed primarily by `kind`, falling back to `ui_kind`

`src/components/editor/registry.ts` maintains two maps:

- `kindRegistry: Map<EntityKind, Component>`
- `uiKindRegistry: Map<UiKind, Component>`

Resolution order: kind registry → ui_kind registry via `uiKindFor(kind)` → `FormEditor`. Export `registerKindEditor`, `registerUiKindEditor`, `resolveEditorForEntity`.

Rationale: satisfies both “by kind” and “by ui_kind” requirements and keeps future decoupling possible.

### 6. Tabs with `KeepAlive` around a dynamic component

`EditorTabsStore` stores open tabs as `{ entityId, title }[]` plus `activeEntityId`. The workspace renders:

```vue
<KeepAlive :include="tabComponentNames">
  <component :is="currentEditorComponent" :key="activeTab.entityId" />
</KeepAlive>
```

Each tab’s editor is a unique component instance keyed by `entityId`; inactive instances are cached by `KeepAlive` and not rebuilt. Closable tabs mutate the store; closing the active tab activates a neighbor.

### 7. Lock and presence as reactive stores, not component subscriptions

- `LocksStore`: `Record<dataPath, LockInfo>`; updated by `locked`, `unlocked`, `lock_denied`; exposes `isLocked(entityId, dataPath)`, `holderOf(...)`.
- `PresenceStore`: `PresenceUser[]`; exposes `usersByEntity(entityId)`, `userAtPath(entityId, dataPath)`.

Field editors use these stores via composables. Components do not subscribe to WS directly; stores own subscriptions to `SyncClient`.

### 8. File manager uses a new REST list endpoint

Add `GET /api/files` returning `{ files: FileRecord[] }` sorted by `created_at DESC`. Frontend `client/rest/files.ts` adds `listFiles`, `uploadFile`, `downloadFile`, `deleteFile`. The file manager panel refreshes after upload/delete.

### 9. CodeMirror 6 for code editors

Add `codemirror`, `@codemirror/lang-python`, `@codemirror/state`, `@codemirror/view`, and a Vue wrapper component. Content saves through the normal lock → patch flow; a debounce (e.g. 500ms) avoids sending every keystroke.

## Risks / Trade-offs

- **localStorage quota** → Catch `QuotaExceededError`, keep in-memory store working, and log a warning; persistence is a cache, not a source of truth.
- **KeepAlive memory growth with many open tabs** → Lock a reasonable tab limit or rely on manual close; keep the cache keyed by entity id so unused tabs can be evicted naturally when closed.
- **Protocol ref extension is a backend change** → Keep new fields optional and ignore unknown refs in existing clients; validate with existing WS tests.
- **Presence stale after closing last tab** → The new `focus {entity_id: null}` clear semantics handles it; older server versions would need the client to keep a fallback focus.
- **Large Python content in entity store/localStorage** → Size is bounded by project scale; if quota becomes a real issue, later we can persist only the vector and refetch full entities on rejoin.

## Migration Plan

- Backend changes are additive: new `GET /api/files`, optional `ref` fields, `focus {entity_id: null}`. Existing endpoints/messages remain compatible.
- Frontend changes are new routes/features; auth pages remain intact.
- Rollback: frontend can be reverted to previous commit; backend additions are harmless if unused.

## Open Questions

None that would change the specs/approach; implementation details such as exact visual styling for lock overlays and presence badges can be decided during implementation.