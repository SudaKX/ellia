## Why

在 M2 前端编辑器基础功能完成后，对实体编辑体验进行细化：补充字段格式校验、优化创建/编辑表单、增强 action bar 功能、改进协作 UI 反馈。

## What Changes

- **Validation 对齐**：`validation_id` 格式宽松为 `[a-zA-Z0-9_-]{1,64}`，添加 `format` 正则校验到 `FieldSpec`，编辑器中不匹配时确认按钮禁用
- **表单 FieldSpec 扩展**：新增 `format` 可选字段（仅 `type=string`），支持正则即时校验
- **随机生成面板**：新增右侧工具面板，支持 UUID v4、kebab-case、snake_case、随机字母数字、SHA-256、Base64、UUID v5
- **实体注释字段**：`entities` 表新增 `comment TEXT` 列；实体卡片展示首行注释；ActionBar 展示完整注释并支持编辑
- **ActionBar 增强**：resource_id 改为可点击编辑（仅 id 部分），两行布局（第一行：resource_id/kind/version/revision/按钮，第二行：注释区）
- **LockOverlay 组件提取**：从 FormField 中提取独立 `LockOverlay.vue` 组件，供 ActionBar 等复用
- **删除实体 UI 通知**：被删除实体的 tab 显示覆盖层提示"已删除"
- **回退错误模态框**：版本回退失败时弹出模态对话框，不再内联显示
- **简化实体 state**：移除 `inject_id` 逻辑，移除 state 中冗余字段（`stable_id`、`account_id` 等由 `resource_id` 导出时解析）
- **ModalDialog 指针事件修复**：按下和松开都在弹窗区域外才关闭，修复拖拽误触
- **服务端 `validateStateShape` 重构**：统一使用 `requiredString()` 辅助函数，`null`/`undefined` 拒绝但空字符串允许

## Capabilities

### New Capabilities
- `entity-editor-validation`: 字段格式校验、formSpec format 扩展、validation_id 对齐
- `entity-editor-random-panel`: 随机生成工具面板
- `entity-editor-comment`: 实体注释字段（数据库、服务端、前端）
- `entity-editor-actionbar`: ActionBar 两行布局、resource_id 编辑、comment 编辑
- `entity-editor-lock-overlay`: LockOverlay 组件提取
- `entity-editor-deleted-ui`: 删除实体通知 UI

### Modified Capabilities
- `entity-sync`: 支持 `data_path` root 新增 `comment`；`EntityRecord` 增加 `comment` 字段；`CreateMessage` 增加 `comment` 可选字段
- `editor-workspace`: 新增 `LockOverlay` 组件、ActionBar 增强、deleted 实体覆盖层

## Impact

- **服务端**：migration v5（`entities.comment`）、`entities.ts` `validateStateShape` 重构、`applyDataPath` 支持 `@comment:` root、`EntityRow`/`CreateEntityInput` 增加 `comment`
- **共享包**：`types.ts` `Entity`/`EntityRecord` 增加 `comment`；`validate.ts` `ParsedDataPath.root` 增加 `comment`；`sync.ts` `CreateMessage` 增加 `comment?`
- **前端**：`FieldEditDialog` 增加 `format` 校验；`RandomPanel.vue` 新增；`EditorActionBar.vue` 重写；`LockOverlay.vue` 新增；`EditorPaneHost.vue` 增加 deleted 覆盖层；`EntityCard.vue` 增加 comment 显示；`CreateEntityPanel.vue` 增加 comment 输入；`createTemplates.json` 移除 `inject_id`；`formSpecs.json` 移除冗余字段；`tokens.css` 调整 `--app-warning` 颜色