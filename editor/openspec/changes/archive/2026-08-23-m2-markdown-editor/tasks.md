## 1. Schema

- [x] 1.1 Add `markdown` to `ENTITY_KINDS`, `UI_KINDS`, `REGISTRY_OF_KIND`, `UI_KIND_OF_KIND`, and `NAMESPACE_OF_KIND` in `packages/puzzle-schema`
- [x] 1.2 Add `MarkdownSegment` and `MarkdownState` types to `packages/puzzle-schema`
- [x] 1.3 Add `MarkdownState` to `EntityState` union and `KindStateMap`

## 2. Server Validation

- [x] 2.1 Add `markdown` case to `validateStateShape` in `apps/server/src/services/entities.ts`
- [x] 2.2 Add markdown create/validation tests to `apps/server/tests/entities.test.ts`

## 3. Dependencies and Theme

- [x] 3.1 Add `markdown-it` dependency to `apps/web`
- [x] 3.2 Add `@codemirror/lang-markdown` dependency to `apps/web`
- [x] 3.3 Add `buildMarkdownHighlight` and `markdownHighlight` to `apps/web/src/stores/style.ts`

## 4. Markdown Editor

- [x] 4.1 Create `render.ts` with markdown-it renderer (`html: false`)
- [x] 4.2 Create `useMarkdown.ts` with `sortedSegments` and `moveSegmentInSort`
- [x] 4.3 Create `MarkdownCodeEditor.vue` using CodeMirror markdown language and M3 theme/highlight
- [x] 4.4 Create `MarkdownSegmentCard.vue` with preview, probe edit button, edit mode, segment lock, save/delete/move/cancel
- [x] 4.5 Create `MarkdownEditor.vue` with vertical flex, TransitionGroup, add-segment FAB, and multi-step lock/patch operations
- [x] 4.6 Register `MarkdownEditor` in `apps/web/src/components/editor/registry.ts`

## 5. Templates and Docs

- [x] 5.1 Add markdown create template to `apps/web/src/config/createTemplates.json`
- [x] 5.2 Update `asset.source_reference` description in `packages/puzzle-schema` and `apps/web/src/config/formSpecs.json`
- [x] 5.3 Update `docs/entity-editor-todo.md` with markdown status and editor details

## 6. Verification

- [x] 6.1 Run `pnpm --dir apps/web type-check`
- [x] 6.2 Run `pnpm --dir apps/web build`
- [x] 6.3 Run `pnpm --dir apps/server test`
