## 1. Schema

- [x] 1.1 Add `questionnaire` to `ENTITY_KINDS` and `UI_KINDS` in `packages/puzzle-schema/src/types.ts`
- [x] 1.2 Add `markdown` and `questionnaire` to `REGISTRY_NAMES`; set `REGISTRY_OF_KIND.markdown` to `markdown` and `REGISTRY_OF_KIND.questionnaire` to `questionnaire`
- [x] 1.3 Add `questionnaire` to `UI_KIND_OF_KIND` and `NAMESPACE_OF_KIND` with `ui_kind: 'questionnaire'` and `namespace: 'source'`
- [x] 1.4 Add `QuestionnaireState`, `QuestionnaireQuestion`, `ChoiceQuestionData`, `TextQuestionData`, and `QuestionType` types
- [x] 1.5 Add `QuestionnaireState` to `EntityState` union and `KindStateMap`

## 2. Server Validation

- [x] 2.1 Add `case 'questionnaire'` to `validateStateShape` in `apps/server/src/services/entities.ts`
- [x] 2.2 Validate `description` is a required string, `sort` is a non-duplicate string array that fully covers `questions`, and each question `id` matches its key
- [x] 2.3 Validate `type` is `choice` or `text`; validate `choice` data has boolean `single` and string array `options`; validate `text` data has `format` null or string
- [x] 2.4 Add server tests for valid questionnaire creation with `source:` namespace
- [x] 2.5 Add server tests for invalid questionnaire state (bad type, bad data, duplicate sort, incomplete sort, mismatched id, wrong namespace)

## 3. Create Template

- [x] 3.1 Add `questionnaire` template to `apps/web/src/config/createTemplates.json` with namespace `source` and default `{ "description": "", "sort": [], "questions": {} }`

## 4. Questionnaire Editor Components

- [x] 4.1 Create `apps/web/src/components/editor/panes/questionnaire/useQuestionnaire.ts` with `sortedQuestions` and `moveQuestionInSort`
- [x] 4.2 Create `QuestionnaireEditor.vue` with questionnaire description card, `TransitionGroup` question list, and sticky `＋ 添加问题` FAB
- [x] 4.3 Create `QuestionCard.vue` with preview/edit mode, question-level lock, actionbar, `LockOverlay`, and draft reset on cancel/unmount/deactivate
- [x] 4.4 Create `ChoiceQuestionPreview.vue` rendering radio options when `single` is true and checkbox options when `single` is false
- [x] 4.5 Create `ChoiceQuestionEditor.vue` editing `single` and an `options` string list with add/remove
- [x] 4.6 Create `TextQuestionPreview.vue` rendering an input sample and a regex format hint when `format` is present
- [x] 4.7 Create `TextQuestionEditor.vue` editing `format` as an optional string, treating empty/null as no validation
- [x] 4.8 Reuse `markdown/MarkdownCodeEditor.vue` for question and description markdown editing and `markdown/render.ts` for preview rendering

## 5. Registry Integration

- [x] 5.1 Import and register `QuestionnaireEditor` for `questionnaire` kind and `questionnaire` ui_kind in `apps/web/src/components/editor/registry.ts`

## 6. Sync and Lock Flows

- [x] 6.1 Implement `applyLocalPatch` pattern for every patch/remove in the questionnaire editor
- [x] 6.2 Implement add question as multi-step patch: write `questions/<uuid>`, then append to `sort`
- [x] 6.3 Implement delete question as remove `questions/<uuid>` then update `sort`
- [x] 6.4 Implement move up/down by patching `sort` only; re-acquire the question lock if the moved question is being edited
- [x] 6.5 Use `@state:/questions/<uuid>` for question locks, `@state:/description` for the questionnaire description lock, and `@state:/sort` for order locks
- [x] 6.6 Unlock and reset drafts on cancel, save failure, lock conflict, unmount, and deactivate

## 7. Verification and Documentation

- [x] 7.1 Run `pnpm --dir apps/web type-check`, `pnpm --dir apps/web build`, and `pnpm --dir apps/server test`
- [x] 7.2 Update `docs/entity-editor-todo.md` with questionnaire progress and markdown registry change
- [x] 7.3 Archive the OpenSpec change after implementation using `/openspec-archive-change`
