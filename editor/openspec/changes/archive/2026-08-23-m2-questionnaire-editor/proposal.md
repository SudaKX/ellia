## Why

编辑器缺少问卷（questionnaire）实体类型，无法以结构化的选择题/填空题形式编辑问卷内容并作为 source 命名空间下的源文件参与导出。需要提供专属编辑器、显式题目顺序、题目级锁和 M3 风格的编辑体验；同时将 markdown 与 questionnaire 从 files 分组中拆分为独立注册表分组，避免源文件类 kind 共用同一分组。

## What Changes

- 新增 `questionnaire` 实体 kind 与 `questionnaire` ui_kind，namespace 使用已有的 `source`。
- 新增 `QuestionnaireState`：
  - `description: string`：问卷整体说明，markdown 文本；
  - `sort: string[]`：显式题目 UUID 顺序；
  - `questions: Record<UUID, QuestionnaireQuestion>`：题目表。
- 新增 `QuestionnaireQuestion`：
  - `id: string`：与 `questions` key 一致；
  - `type: 'choice' | 'text'`：选择题 / 填空题；
  - `description: string`：题目说明，markdown 文本；
  - `data`：按 type 分支：
    - `choice`: `{ single: boolean, options: string[] }`
    - `text`: `{ format: string | null }`
- 新增服务端 `questionnaire` state 校验：`description` 必填 string，`sort` 无重复且完整覆盖 `questions`，question `id` 与 key 一致，`type` 合法，`data` 按 type 校验。
- 注册表调整：
  - `REGISTRY_NAMES` 新增 `markdown`、`questionnaire`；
  - `REGISTRY_OF_KIND.markdown` 从 `files` 改为 `markdown`；
  - `REGISTRY_OF_KIND.questionnaire` 设为 `questionnaire`。
- 新增创建模板：`source:xxx`，默认 `{ description: "", sort: [], questions: {} }`。
- 新增专属 QuestionnaireEditor：
  - 问卷说明卡片 + `TransitionGroup` 题目卡片列表；
  - 题目卡片默认预览：上部 markdown 渲染 description，下部按 type 渲染题目预览；
  - 编辑模式：description 使用 CodeMirror markdown 编辑，type 使用下拉选择，data 按 type 切换编辑组件；
  - 题目级锁 `@state:/questions/<uuid>`，说明锁 `@state:/description`，排序锁 `@state:/sort`；
  - 支持添加、删除、上移/下移、确定、取消；
  - 右下角 M3 FAB 添加题目。

## Capabilities

### New Capabilities

- `questionnaire-editor`: questionnaire 实体类型、题目 state、服务端校验、专属编辑器、题目级锁与两类题目的预览/编辑组件。

### Modified Capabilities

- `markdown-editor`: markdown 的注册表分组从 `files` 调整为独立 `markdown` 注册表；namespace、state、编辑器行为不变。

## Impact

- `packages/puzzle-schema`：新增 `questionnaire` kind/ui_kind、`QuestionnaireState`/`QuestionnaireQuestion` 类型；`REGISTRY_NAMES` 新增 `markdown`/`questionnaire`；`REGISTRY_OF_KIND` 调整 markdown 并新增 questionnaire。
- `apps/server`：`validateStateShape` 新增 questionnaire 校验；测试补充。
- `apps/web`：
  - 新增 `QuestionnaireEditor`、`QuestionCard`、选择题/填空题预览与编辑组件、useQuestionnaire 工具；
  - 复用 `MarkdownCodeEditor`、markdown-it 渲染、`DropdownSelect`、`LockOverlay`；
  - `registry.ts` 注册 questionnaire 编辑器；
  - `createTemplates.json` 新增模板。
- 文档：`docs/entity-editor-todo.md` 更新 questionnaire 与 markdown 注册表进度。
