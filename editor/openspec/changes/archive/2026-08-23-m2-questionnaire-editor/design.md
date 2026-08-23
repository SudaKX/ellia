## Context

编辑器已有通用实体同步、字段级/段级锁、专用编辑器（FileTree/DAG/Markdown）和 CodeMirror 基础。`source` namespace 已被 markdown 使用；问卷同样属于 source 源文件类实体，但 kind 不同。当前 `REGISTRY_OF_KIND` 仅用于 schema 分组语义，前端实体浏览器实际按 `entity.kind` / `entity.group` 筛选，因此调整注册表不会改变现有运行时行为。

## Goals / Non-Goals

**Goals:**

- 新增 `questionnaire` 实体类型，使用 `source` namespace。
- 使用显式 `sort` 数组表达题目顺序。
- 提供题目级锁、markdown 预览/编辑、选择题/填空题预览与编辑组件、增删和排序操作。
- 将 markdown 与 questionnaire 从 `files` 注册表拆分为独立注册表 `markdown` / `questionnaire`。
- 保持与现有编辑器的 M3 主题、锁模式和 WS 多步 patch 风格一致。

**Non-Goals:**

- 不做拖拽排序（先提供上移/下移）。
- 不做玩家侧真实作答、提交/计分逻辑，只做题目编辑与预览。
- 不做导出阶段把问卷写入实际文件/生成 mythos FileReference 的管线。
- 不做富文本编辑器、协同光标、评论等高级能力。

## Decisions

### 使用 `sort: string[]` 而非每题数字 `sort`

- 选择显式 UUID 数组作为唯一顺序来源。
- 理由：重排只需 patch 一个 `sort` 数组，不依赖多个题的数字字段；与 `MarkdownState.sort` 一致。
- 备选：每题 `sort: number`，但重排需要更新多个题，锁冲突面更大。

### 注册表新增 `markdown` / `questionnaire`，不复用 `files`

- `REGISTRY_NAMES` 新增 `markdown`、`questionnaire`；`REGISTRY_OF_KIND.markdown` 改为 `markdown`，`REGISTRY_OF_KIND.questionnaire` 设为 `questionnaire`。
- 理由：虽然 namespace 都是 `source`，但 kind 不同，未来若实体树按 registry 分组，应各自独立成组；当前没有运行时读取该映射，改动安全。
- 备选：继续共用 `files`，实现更少但语义上把不同 kind 混在同一分组。

### 使用 `type: 'choice' | 'text'` 表达题目类型

- `choice` data：`{ single: boolean, options: string[] }`
- `text` data：`{ format: string | null }`
- 理由：覆盖用户要求的选择题/填空题两种形态；`single` 区分单选/多选；`format` 为 null 或空字符串时不校验格式。
- 备选：`single` 作为独立顶层字段，但会破坏“data 随 type 变化”的统一结构。

### 题目级锁 + 多步 patch

- 每个 question 使用 `entity@state:/questions/<uuid>` 作为锁路径；顺序使用 `entity@state:/sort`；问卷说明使用 `entity@state:/description`。
- 编辑/删除锁 question；移动锁 `sort`；添加先写 question 再写 `sort`。
- 理由：与 MarkdownEditor 的段级锁和 WS patch 模式一致，避免整实体大锁。
- 备选：整 state 锁更简单但会阻塞其他题目的协作编辑。

### 卡片默认预览，编辑时整题锁定

- 预览模式：上部 markdown 渲染 `description`，下部按 type 渲染题目预览。
- 编辑模式：整题作为编辑单元，一次锁定 `questions/<uuid>`，内部编辑 description、type、data。
- 理由：`type` 切换会影响 `data` 结构，整题锁比字段级锁更简单，也符合“锁粒度到题目”的要求。
- 备选：description/type/data 分别锁，协作粒度更细但锁管理和数据一致性更复杂。

### 复用现有 Markdown 与 UI 组件

- Markdown 渲染复用 `markdown/render.ts`（`markdown-it` + `html: false`）。
- Markdown 编辑复用 `markdown/MarkdownCodeEditor.vue`（CodeMirror + M3 主题）。
- type 下拉复用 `ui/DropdownSelect.vue`。
- 锁遮罩复用 `presence/LockOverlay.vue`。
- 理由：避免重复实现，保持视觉和交互一致。

### 选择题 options 编辑为文本行列表

- 编辑组件提供逐行 option 输入，支持添加/删除；`single` 用开关/复选框切换。
- 理由：简单直接，符合 M3 表单风格；预览时按 `single` 渲染 radio/checkbox。

## Risks / Trade-offs

- [多步 patch 非原子] → 添加/删除过程中如果第二步失败，可能出现 `questions` 与 `sort` 短暂不一致；现有 Markdown/FileTree/DAG 也有类似多步操作，后续可增加补偿/重试。
- [移动时锁切换存在窗口] → 移动会从 question 锁切到 sort 锁再切回 question 锁，极小窗口内其他用户可能抢锁；当前单连接单锁约束下可接受。
- [markdown-it 渲染 XSS] → 使用 `html: false` 默认转义原始 HTML，预览保持安全。
- [注册表新增名称偏离 Mythos 固定注册表] → 当前 `REGISTRY_OF_KIND` 无运行时消费者；若未来 Mythos 导出按注册表名映射，需要同步 Mythos 侧注册表定义。
- [前端包体积增加] → 新增组件和复用 CodeMirror/markdown-it 已有依赖；当前可接受，后续可考虑动态导入。

## Migration Plan

1. 新增 schema 类型、服务端校验、创建模板和编辑器，均向后兼容（新增 kind，不影响已有实体）。
2. `REGISTRY_OF_KIND.markdown` 从 `files` 改为 `markdown` 只影响 schema 映射，无需数据库迁移。
3. 回滚策略：移除 questionnaire 注册/路由/模板即可；markdown 的 registry 改动可回退为 `files`。
4. 无需数据库迁移，实体仍存储在通用 entities 表中。

## Open Questions

- 是否要求选择题至少有一个非空 option；当前 spec 只要求 `options` 为 string[]，可后续收紧。
