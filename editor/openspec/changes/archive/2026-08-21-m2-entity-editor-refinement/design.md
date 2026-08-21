## Context

本 change 是在 M2 前端编辑器基础上对实体编辑体验的细化（动机见 proposal.md）。现有系统已具备：WS v2 同步、字段锁、presence、结构化表单、实体浏览器、多标签编辑器。本设计聚焦于新增 comment 字段的数据链路、FieldSpec format 校验机制、ActionBar 重写和 LockOverlay 复用。

## Goals / Non-Goals

**Goals:**
- 用最小的 schema 改动（`comment` 列 + `data_path` root）支持实体注释
- 将字段格式校验从组件内散落的逻辑收敛到 `FieldSpec.format` 配置驱动
- 复用 LockOverlay 组件避免三处重复实现（FormField / resource_id / comment）
- 保持向后兼容：已有实体的 state 不含冗余字段也可正常渲染

**Non-Goals:**
- 不做 `comment` 的富文本或 Markdown 渲染
- 不做随机生成与表单的深度联动（如弹窗内嵌生成按钮）
- 不引入 slot 过滤机制（后端无 slot 概念）
- 不做既有数据的迁移（旧数据 state 中残留的 `stable_id` 等字段被忽略）

## Decisions

### D1: comment 作为实体列而非 state 字段

将 `comment` 作为 `entities` 表独立列（migration v5），而非放入 `state` JSON。

- **理由**：`comment` 是实体级元数据，不属于某个 kind 的业务状态；放入 state 会污染 `KindStateMap` 类型，且所有 kind 都需要它。独立列 + `data_path` root 方式与 `group`、`resource_id` 一致。
- **替代方案**：放入 state 顶层 `{...state, _comment}`。被否：会破坏 `validateStateShape` 对 state 形状的严格校验，且导出时需特殊剥离。

### D2: data_path 增加 `comment` root

`ParsedDataPath.root` 从 `'state' | 'group' | 'resource_id'` 扩展为 `'state' | 'group' | 'resource_id' | 'comment'`，与 `group`/`resource_id` 一样 json_path 为空。

- **理由**：复用既有字段锁、patch 广播、STALE_LOCK 校验全套机制，无需为 comment 单独设计同步协议。
- **替代方案**：新增独立 WS 消息 `set_comment`。被否：增加协议复杂度，且锁/历史/广播逻辑重复。

### D3: FieldSpec.format 配置驱动校验

`FieldSpec` 新增 `format?: string`（仅 `type=string` 有效），在 `FieldEditDialog` 中构造正则、不匹配时禁用确认按钮并显示错误。`validation.validation_id` 使用 `^[a-zA-Z0-9_-]{1,64}$`。

- **理由**：把校验规则从代码散落处收敛到 `formSpecs.json` 配置，新增字段无需改组件。
- **替代方案**：在 `FieldEditDialog` 硬编码 validation 特判。被否：不可扩展，其他字段无法复用。

### D4: LockOverlay 组件提取

将 `FormField.vue` 中的 `form-field__lock-overlay` + `form-field__lock-tag` 结构提取为 `presence/LockOverlay.vue`，接受 `username` prop。

- **理由**：ActionBar 的 resource_id 按钮和注释 surface 也需要相同的锁定覆盖层，避免三份重复 CSS/DOM。
- **替代方案**：仅复制粘贴。被否：三处样式漂移风险高。

### D5: deleted 实体 UI 基于显式标记

在 `entitiesStore` 增加 `deletedEntityIds: Set<string>`，`applyDeleted()` 记录被删 id；`EditorPaneHost` 通过 `isDeleted` 计算属性显示覆盖层。不用"实体不存在即已删除"的隐式推导。

- **理由**：语义对齐——实体可能因重连 `sync` 未包含而暂时缺失，显式标记避免误报"已删除"。

### D6: 移除 inject_id 与冗余 state 字段

`createTemplates.json` 移除 `inject_id` 配置；`types.ts` 中 `stable_id`、`account_id` 等 12 个字段标记为 `@deprecated` + 可选。导出时从 `resource_id` 解析。

- **理由**：state 中冗余字段与 `resource_id` 是同一信息的两份拷贝，容易产生不一致（修改 state 不影响 resource_id）。保留字段类型为可选以兼容旧数据。

## Risks / Trade-offs

- [comment 列新增导致旧库需迁移] → migration v5 提供 `DEFAULT ''`，向后兼容；已存在的 DB 会自动执行。
- [移除 inject_id 后旧前端缓存可能有残留字段] → 共享类型字段标记可选，渲染时忽略未知字段，不报错。
- [format 正则来自 JSON 配置，可能非法] → `FieldEditDialog` 用 try/catch 构造正则，非法时提示"格式配置无效"并禁用确认。
- [ActionBar 两行布局在窄屏可能挤压] → 第一行使用 `overflow-x: auto`，注释区第二行可换行。

## Migration Plan

1. 服务端 migration v5 增加 `entities.comment` 列（已实现）。
2. 前端共享类型同步 `Entity`/`EntityRecord`/`CreateMessage` 增加 `comment`。
3. 逐步移除 `inject_id`（`createTemplates.json`、`CreateEntityPanel.vue`、`createTemplates.ts`）。
4. 已有数据不迁移：state 中的旧冗余字段被忽略，导出逻辑改为从 `resource_id` 解析。

## Open Questions

无。