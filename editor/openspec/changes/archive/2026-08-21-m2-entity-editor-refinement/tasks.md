## 1. 共享类型与服务端

- [x] 1.1 `types.ts`：`Entity`/`EntityRecord` 增加 `comment: string`
- [x] 1.2 `sync.ts`：`CreateMessage` 增加 `comment?: string`
- [x] 1.3 `validate.ts`：`ParsedDataPath.root` 增加 `'comment'`；`parseDataPath` 支持 `comment` root
- [x] 1.4 migration v5：`entities` 表增加 `comment TEXT NOT NULL DEFAULT ''`
- [x] 1.5 `entities.ts`：`EntityRow`、`CreateEntityInput` 增加 `comment`；`toEntity`/`toEntityRecord` 透传
- [x] 1.6 `entities.ts`：`createEntity` INSERT 包含 `comment`
- [x] 1.7 `entities.ts`：`applyDataPath` 支持 `@comment:` root（校验字符串、禁止 remove）
- [x] 1.8 `entities.ts`：`patchEntity` UPDATE 包含 `comment`
- [x] 1.9 `hub.ts`：`handleCreate` 透传 `message.comment`

## 2. validateStateShape 重构

- [x] 2.1 提取 `requiredString(field, label)` 辅助函数：`undefined`/`null` 拒绝，空字符串允许
- [x] 2.2 所有 16 个 kind 统一使用 `requiredString`（移除 `!state.field` 旧检查）
- [x] 2.3 `hint.display.title` 改用 split 检查（undefined/null 必填 + 类型检查）
- [x] 2.4 移除 `inject_id` 相关字段的 `requiredString` 检查（`stable_id`、`account_id` 等 12 个）

## 3. FieldSpec format 校验

- [x] 3.1 `formTypes.ts`：`FieldSpec` 增加 `format?: string`
- [x] 3.2 `FieldEditDialog.vue`：构造正则、格式错误提示、确认按钮禁用
- [x] 3.3 `ModalDialog.vue`：增加 `confirmDisabled` prop
- [x] 3.4 `formSpecs.json`：`validation.validation_id` 增加 `format: "^[a-zA-Z0-9_-]{1,64}$"` 且必填
- [x] 3.5 `createTemplates.json`：`validation.handler_block_id` 默认空字符串

## 4. 随机生成面板

- [x] 4.1 `utils/random.ts`：随机 UUID v4、kebab-case、snake_case、字母数字、SHA-256、Base64、UUID v5
- [x] 4.2 `RandomPanel.vue`：纯随机 + 基于原数据两个区域、复制按钮
- [x] 4.3 `toolPanel.ts`：`ToolId` 增加 `'random'`
- [x] 4.4 `ToolRail.vue`：增加"随机生成 🎲"按钮
- [x] 4.5 `EditorLayout.vue`：接入 `RandomPanel`

## 5. 实体注释

- [x] 5.1 `EntityCard.vue`：展示 `comment` 第一行
- [x] 5.2 `EditorActionBar.vue`：注释 surface 展示 + 编辑/添加按钮 + 模态对话框
- [x] 5.3 `CreateEntityPanel.vue`：增加注释 textarea，创建时随 `create` 发送
- [x] 5.4 `entitiesStore`：`applyUpdate` 支持 `comment` root

## 6. LockOverlay 提取

- [x] 6.1 `presence/LockOverlay.vue`：独立覆盖层组件（username prop）

## 7. ActionBar 增强

- [x] 7.1 resource_id 可点击编辑（仅 id 部分，namespace 不可改）
- [x] 7.2 两行布局：第一行元数据+按钮，第二行注释 surface
- [x] 7.3 注释 surface 无注释时虚线边框+半透明，完整展示多行
- [x] 7.4 `EditorTabBar.vue`：标签标题从 entities store 实时读取，resource_id 修改后同步
- [x] 7.5 回退错误改用模态对话框

## 8. 删除实体 UI

- [x] 8.1 `entitiesStore`：`deletedEntityIds` Set + `applyDeleted` 记录
- [x] 8.2 `EditorPaneHost.vue`：被删除实体覆盖层 + 关闭标签按钮

## 9. 通用修复

- [x] 9.1 `ModalDialog.vue`：pointerdown/pointerup 双击区域外才关闭（修复拖拽误触）
- [x] 9.2 `tokens.css`：`--app-warning` 浅色模式改为 `#c66900`
- [x] 9.3 `FormField.vue`：空字符串 string 字段渲染为空（不再显示"（空）"），警告色描边
- [x] 9.4 `createTemplates.json`：移除所有 `inject_id` 配置和冗余默认字段

## 10. 验证

- [x] 10.1 运行 `pnpm type-check` 通过
- [x] 10.2 运行 `pnpm --dir apps/server test`（71 个用例全绿）
- [x] 10.3 运行 `pnpm build` 通过