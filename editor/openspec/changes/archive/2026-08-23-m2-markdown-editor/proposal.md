## Why

编辑器缺少 markdown 源文件实体类型，无法以分段方式编辑连续 markdown 文本并作为 source 命名空间下的源文件参与导出。需要提供专属编辑器、显式顺序、段级锁和 M3 风格的编辑体验。

## What Changes

- 新增 `markdown` 实体 kind 与 `markdown` ui_kind，namespace 使用已有的 `source`。
- 新增 `MarkdownState`：
  - `sort: string[]`：显式 UUID 顺序；
  - `segments: Record<UUID, { id, content }>`：markdown 文本段。
- 新增服务端 `markdown` state 校验：`sort` 无重复且完整覆盖 `segments`，segment `id` 与 key 一致，`content` 为字符串。
- 新增创建模板：`source:xxx`，默认 `{ sort: [], segments: {} }`。
- 新增专属 MarkdownEditor：
  - 纵向 flex + `TransitionGroup` 卡片列表；
  - markdown-it 渲染预览，兼容 M3 主题；
  - CodeMirror markdown 编辑与语法高亮；
  - 段级锁、右下角探测区、编辑/确定/删除/上移/下移/取消；
  - 右下角 M3 FAB 添加段落。
- 更新 asset 的 `source_reference` 字段说明，明确引用 source 源文件实体（如 markdown）。

## Capabilities

### New Capabilities

- `markdown-editor`: markdown 实体类型、分段 state、服务端校验、专属编辑器与段级锁。

### Modified Capabilities

无。

## Impact

- `packages/puzzle-schema`：新增 `markdown` kind/ui_kind、`MarkdownState`/`MarkdownSegment` 类型、映射关系。
- `apps/server`：`validateStateShape` 新增 markdown 校验；测试补充。
- `apps/web`：
  - 新增 `markdown-it`、`@codemirror/lang-markdown` 依赖；
  - 新增 `MarkdownEditor`、`MarkdownSegmentCard`、`MarkdownCodeEditor`、render/useMarkdown 工具；
  - `stores/style.ts` 新增 markdown 高亮；
  - `registry.ts` 注册 markdown 编辑器；
  - `createTemplates.json` 新增模板；
  - `formSpecs.json` 更新 asset.source_reference 说明。
- 文档：`docs/entity-editor-todo.md` 更新 markdown 进度。
