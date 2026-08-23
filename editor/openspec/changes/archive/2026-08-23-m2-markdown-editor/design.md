## Context

编辑器已有通用实体同步、字段级锁、专用容器编辑器（FileTree/DAG）和 CodeMirror 编辑器基础。当前缺少 markdown 源文件实体；`source` namespace 已存在但尚未被任何 kind 使用。asset 的 `source_reference` 字段已经可以引用 `source` 命名空间，因此新增 markdown 后可直接作为源文件实体被引用。

## Goals / Non-Goals

**Goals:**

- 提供 `markdown` 实体类型，使用 `source` namespace。
- 使用显式 `sort` 数组表达段顺序，避免数值排序的歧义。
- 提供段级锁、预览渲染、CodeMirror 编辑、增删和排序操作。
- 保持与现有编辑器的 M3 主题、锁模式和 WS 多步 patch 风格一致。

**Non-Goals:**

- 不做拖拽排序（先提供上移/下移）。
- 不做导出阶段把 markdown 写入实际文件/生成 mythos FileReference 的管线。
- 不做富文本编辑器、协同光标、评论等高级能力。

## Decisions

### 使用 `sort: string[]` 而非每段数字 `sort`

- 选择显式 UUID 数组作为唯一顺序来源。
- 理由：重排只需 patch 一个 `sort` 数组，不依赖多个段的数字字段；与 `DagState.entryIds` 的既有模式一致。
- 备选：每段 `sort: number`，但重排需要更新多个段，锁冲突面更大。

### 使用 markdown-it 渲染预览

- 选择 `markdown-it`（参考 `.ref/markdown-it`），配置 `html: false, linkify: true`。
- 理由：安全默认、CommonMark 支持好、体积/性能适合编辑器预览。
- 备选：自己实现渲染或引入重级编辑器，成本和风险更高。

### 使用 CodeMirror + `@codemirror/lang-markdown` 编辑

- 选择复用现有 CodeMirror 基础设施，新增 markdown 语言支持和 M3 高亮。
- 理由：与 CodeEditor/JsonEditor 一致，主题、只读切换、快捷键体验统一。
- 备选：textarea 无语法高亮，不符合编辑体验要求。

### 段级锁 + 多步 patch

- 每个 segment 使用 `entity@state:/segments/<uuid>` 作为锁路径；顺序使用 `entity@state:/sort`。
- 编辑/删除锁 segment；移动锁 `sort`；添加先写 segment 再写 `sort`。
- 理由：与 FileTree/DAG 的现有锁和 WS patch 模式一致，避免引入整实体大锁。
- 备选：整 state 锁更简单但会阻塞其他段的协作编辑。

### 右下角 M3 FAB 添加段落

- 选择 sticky 右下角 primary FAB。
- 理由：符合 M3 风格，不占用卡片列表顶部空间，滚动时保持可见。

## Risks / Trade-offs

- [多步 patch 非原子] → 添加/删除过程中如果第二步失败，可能出现 `segments` 与 `sort` 短暂不一致；现有 FileTree/DAG 也有类似多步操作，后续可增加补偿/重试。
- [移动时锁切换存在窗口] → 移动会从 segment 锁切到 sort 锁再切回 segment 锁，极小窗口内其他用户可能抢锁；当前单连接单锁约束下可接受。
- [markdown-it 渲染 XSS] → 使用 `html: false` 默认转义原始 HTML，预览保持安全。
- [前端包体积增加] → markdown-it + markdown language 增加主包体积；当前可接受，后续可考虑动态导入。

## Migration Plan

1. 新增 schema 类型、服务端校验、创建模板和编辑器，均向后兼容（新增 kind，不影响已有实体）。
2. 回滚策略：移除 markdown 注册/路由/模板即可，不影响其他实体类型。
3. 无需数据库迁移，实体仍存储在通用 entities 表中。
