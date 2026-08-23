# 自定义实体编辑器 SOP（Agent 参考）

> 目标：新增一种实体 kind / ui_kind 并实现专属编辑器时，按本 SOP 接入 `registry.ts`、处理 WS 同步与字段/段级锁，并补齐服务端校验、创建模板、测试和 OpenSpec 文档。

## 1. 相关背景

### 1.1 实体模型与 ui_kind

- 实体模型定义在 `packages/puzzle-schema/src/types.ts`。
- 每个实体有：
  - `kind`：实体种类，如 `markdown`、`dag`、`code`
  - `ui_kind`：前端展示类型，决定使用哪个编辑器组件，如 `markdown`、`dag`、`code`、`form`
  - `resource_id`：`<namespace>:<id>`，namespace 由 `NAMESPACE_OF_KIND` 决定
  - `state`：权威状态，类型由 `KindStateMap[kind]` 约束
- 新增 kind 通常需要同步修改：
  - `ENTITY_KINDS`
  - `UI_KINDS`
  - `REGISTRY_OF_KIND`
  - `UI_KIND_OF_KIND`
  - `NAMESPACE_OF_KIND`
  - `EntityState` 联合类型
  - `KindStateMap`

### 1.2 同步基础（WS v2）

- 前端通过 `apps/web/src/client/ws/SyncClient.ts` 与后端通信。
- 常用方法：
  - `syncClient.create(...)`
  - `syncClient.patch(entityId, dataPath, value, op?)`
  - `syncClient.removeField(entityId, dataPath)`
  - `syncClient.lock(entityId, dataPath)`
  - `syncClient.unlock(entityId, dataPath)`
  - `syncClient.focus(entityId, dataPath?)`
- `data_path` 格式：`<entity_id>@<root>:<json_path>`
  - root 通常为 `state`
  - 整个 state：`<entity_id>@state:`
  - 字段：`<entity_id>@state:/field`
  - 嵌套：`<entity_id>@state:/segments/<uuid>`
- **重要**：发送方不会收到自己的 `update` 广播，因此每次 patch 后需要手动调用 `entitiesStore.applyUpdate(...)` 应用本地状态（见 1.4）。

### 1.3 锁模型

- 锁存储在服务端，前端通过 `apps/web/src/stores/locks.ts` 读取。
- 规则：
  - 每个连接同一时间只能持有一个锁；锁定新路径会顶替旧锁。
  - `patch` 成功后服务端自动释放该路径的锁。
  - 删除/取消/失败时需要手动 `unlock`。
  - 其他连接持有同一路径锁时，`lock` 会返回 `lock_denied`。
- 前端判断：
  - `locks.holderOf(dataPath)`：获取该路径锁信息
  - `locks.isLocked(entityId, dataPath)`：是否被锁定
  - `locks.lockList`：当前项目全部锁
  - 判断“他人锁”时排除 `auth.user?.id`
- 编辑器应在 `setup`/`onMounted` 调用 `locks.ensureSubscriptions()`。

### 1.4 本地状态更新

- 由于发送方收不到自己的 `update` 广播，编辑器在 patch/remove 后需要手动应用本地更新。
- 参考 FileTree/DAG/Markdown 的 `applyLocalPatch` 模式：

```ts
import type { UpdateMessage } from '@ellia/puzzle-schema'
import { useEntitiesStore } from '../../../stores/entities'

const entitiesStore = useEntitiesStore()

function applyLocalPatch(
  dataPath: string,
  op: 'set' | 'remove',
  value: unknown,
  revision: number,
  version: number,
): void {
  entitiesStore.applyUpdate({
    type: 'update',
    entity_id: props.entity.id,
    revision,
    version,
    data_path: dataPath,
    op,
    ...(op === 'set' ? { value } : {}),
    author: { id: '', username: '' },
  } as UpdateMessage)
}
```

### 1.5 编辑器注册表

- 文件：`apps/web/src/components/editor/registry.ts`
- 注册：
  - `registerKindEditor('my-kind', MyEditor)`
  - `registerUiKindEditor('my-ui-kind', MyEditor)`
- 解析顺序：`kindRegistry` → `uiKindRegistry` → `uiKindFor(kind)` 默认 → `FallbackEditor`
- 若没有专属编辑器，可让 kind 落到 `form` 或 `FallbackEditor`。

### 1.6 创建模板

- 文件：`apps/web/src/config/createTemplates.json`
- `CreateEntityPanel` 使用 `CREATE_TEMPLATES[kind]`，类型为 `Record<EntityKind, CreateTemplate>`。
- 新增 kind 必须补模板，否则 TypeScript 会报错。
- 模板字段：`namespace`、`fixed`、`default`、`comment`。

### 1.7 服务端校验

- 文件：`apps/server/src/services/entities.ts`
- 在 `validateStateShape(kind, state)` 中按 kind 校验 state 最小形状。
- 创建实体时会调用该校验；patch 目前不会全量校验，但编辑器应保证写入后 state 合法。
- 建议补充 `apps/server/tests/entities.test.ts` 的创建/非法 state 用例。

### 1.8 常用 UI 基础

- `LockOverlay.vue`：绝对定位遮罩，显示锁定者；`z-index: 100`，会盖住编辑器内部按钮。
- `LockHint.vue`：行内锁提示，显示路径和用户名。
- `UserBadge`：在场用户头像。
- CodeMirror 编辑器参考：
  - `CodeEditor.vue`（Python）
  - `FallbackEditor.vue`（JSON）
  - `markdown/MarkdownCodeEditor.vue`（Markdown）
- M3 主题：
  - `stores/style.ts` 提供 `editorTheme` 和 `pythonHighlight` / `jsonHighlight` / `markdownHighlight`
  - 创建 CodeMirror 视图时使用 `themeCompartment` / `highlightCompartment` / `editableCompartment`

## 2. SOP 步骤

### Step 1：明确需求并创建 OpenSpec change（可选但推荐）

- 使用 `/openspec-propose` 创建 `m2-<feature>-editor` change。
- 至少包含 proposal、specs、design、tasks。
- 实现完成后使用 `/openspec-archive-change` 同步主 spec 并归档。

### Step 2：定义 Schema

在 `packages/puzzle-schema/src/types.ts`：

1. 添加 `kind` 到 `ENTITY_KINDS`。
2. 添加 `ui_kind` 到 `UI_KINDS`。
3. 更新 `REGISTRY_OF_KIND` / `UI_KIND_OF_KIND` / `NAMESPACE_OF_KIND`。
4. 添加 state 接口，并加入 `EntityState` 与 `KindStateMap`。
5. 如使用已有 namespace（如 `source`），无需修改 `RESOURCE_NAMESPACES`。

### Step 3：后端校验与测试

- 在 `validateStateShape` 添加 `case '<kind>'`。
- 校验必填字段、类型、内部引用/顺序约束。
- 在 `apps/server/tests/entities.test.ts` 添加：
  - 合法创建
  - 非法 state 被拒绝
  - 错误 namespace 被拒绝

### Step 4：创建模板

- 在 `apps/web/src/config/createTemplates.json` 添加 `<kind>` 模板。
- 默认 state 必须能通过服务端校验。

### Step 5：实现编辑器组件

建议目录：

```
apps/web/src/components/editor/panes/<feature>/
  <Feature>Editor.vue      # 主编辑器
  <Feature>Card.vue        # 子卡片/条目（可选）
  <Feature>CodeEditor.vue  # CodeMirror 封装（可选）
  use<Feature>.ts          # 排序/派生/操作辅助
  render.ts                # 渲染辅助（如 markdown-it）
```

主编辑器 props：

```ts
const props = defineProps<{
  entity: EntityRecord
}>()
```

- 使用 `computed` 从 `entity.state` 派生数据。
- 使用 `useEntitiesStore` / `useLocksStore` / `useAuthStore`。
- 调用 `locks.ensureSubscriptions()`。

### Step 6：注册到 registry

- 导入编辑器并注册 kind / ui_kind。
- 若 `ui_kind` 是新增值，确保 schema 中 `UI_KINDS` 已包含。

### Step 7：实现同步与锁流程

#### 7.1 编辑一个字段/段

```ts
const dataPath = `${entity.id}@state:/some/path`

async function startEdit() {
  if (lockedByOther) return
  await syncClient.lock(entity.id, dataPath)
  editing = true
}

async function save() {
  const applied = await syncClient.patch(entity.id, dataPath, nextValue)
  applyLocalPatch(dataPath, 'set', nextValue, applied.revision, applied.version)
  editing = false
}

async function cancel() {
  await syncClient.unlock(entity.id, dataPath).catch(() => undefined)
  editing = false
  resetDraft()
}
```

#### 7.2 新增条目（多步 patch）

```ts
const id = crypto.randomUUID()
const itemPath = `${entity.id}@state:/items/${id}`
const nextOrder = [...state.order, id]

// 先写条目，再写顺序；每步 patch 后手动 applyLocalPatch
await syncClient.lock(entity.id, itemPath)
const appliedItem = await syncClient.patch(entity.id, itemPath, item)
applyLocalPatch(itemPath, 'set', item, appliedItem.revision, appliedItem.version)

await syncClient.lock(entity.id, orderPath)
const appliedOrder = await syncClient.patch(entity.id, orderPath, nextOrder)
applyLocalPatch(orderPath, 'set', nextOrder, appliedOrder.revision, appliedOrder.version)
```

注意：由于单连接单锁，第二步 `lock` 会顶替第一步的锁；第一步 patch 已自动释放锁，所以顺序通常是“patch 后再锁下一个路径”。

#### 7.3 删除条目

- 先 `lock` 条目路径，`removeField`，`applyLocalPatch(remove)`。
- 若还有顺序数组，再 `lock` 顺序路径，`patch` 新数组。
- 删除前检查相关路径是否被他人锁定。

#### 7.4 重排

- 只锁顺序路径（如 `state:/sort`），`patch` 新数组。
- 如果操作来自正在编辑的条目，注意锁会被顶替；必要时操作完成后重新 `lock` 条目路径，让编辑态继续有效。

#### 7.5 整 state JSON 编辑器

- 使用 `FallbackEditor.vue` 或自定义整 state 编辑器。
- 锁路径使用 `<entity_id>@state:`。
- 进入编辑前检查该实体 `@state` 下是否有其他用户锁。
- 取消/失败/切走时重置草稿并释放锁。

### Step 8：展示锁与在场

- 其他用户锁定时：
  - 使用 `LockOverlay` 覆盖卡片/编辑器区域
  - 或使用 `LockHint` 显示具体路径
- 在场提示：
  - `presence.userAtPath(entity.id, dataPath)`
  - 使用 `UserBadge` 展示

### Step 9：样式与 CodeMirror/M3

- 需要代码编辑时参考 `CodeEditor.vue` / `MarkdownCodeEditor.vue`。
- 在 `stores/style.ts` 添加对应语言的 `HighlightStyle`（如 `markdownHighlight`）。
- 使用 `themeCompartment` / `highlightCompartment` 响应 M3 明暗主题变化。
- 渲染富文本（如 markdown）时使用 `markdown-it` 且 `html: false`，用 M3 CSS 变量定制样式。

### Step 10：文档与验证

- 更新 `docs/entity-editor-todo.md`。
- 运行：
  ```powershell
  pnpm --dir apps/web type-check
  pnpm --dir apps/web build
  pnpm --dir apps/server test
  ```
- 若创建了 OpenSpec change，完成 `/openspec-archive-change`。

## 3. 锁与同步速查表

| 操作 | 锁路径 | 成功后 | 失败/取消 |
|---|---|---|---|
| 编辑字段/段 | `entity@state:/path` | patch 自动释放 | unlock |
| 保存 | 同上 | 手动 applyLocalPatch | unlock + 重置草稿 |
| 取消 | 同上 | unlock + 重置草稿 | unlock |
| 新增条目 | 条目路径 + 顺序路径 | 分步 applyLocalPatch | 释放已获取锁 |
| 删除条目 | 条目路径 + 顺序路径 | remove + apply | 释放已获取锁 |
| 重排 | 顺序路径 | patch + apply | 释放顺序锁 |
| 整 state JSON | `entity@state:` | patch + apply | unlock + 重置草稿 |

## 4. 参考实现

- `apps/web/src/components/editor/panes/CodeEditor.vue`：CodeMirror + 单路径锁
- `apps/web/src/components/editor/panes/FallbackEditor.vue`：整 state JSON + 全 state 锁
- `apps/web/src/components/editor/panes/FileTreeEditor.vue`：多步新增/删除 + applyLocalPatch
- `apps/web/src/components/editor/panes/DagEditor.vue`：容器拓扑 + 多路径锁
- `apps/web/src/components/editor/panes/markdown/MarkdownEditor.vue`：显式顺序数组 + 段级锁 + TransitionGroup
- `apps/web/src/components/editor/panes/markdown/MarkdownSegmentCard.vue`：卡片内编辑/删除/移动/取消
- `apps/web/src/components/editor/panes/markdown/MarkdownCodeEditor.vue`：CodeMirror markdown + M3
