# 实体编辑器细化 TODO

> 目标：按实体类型逐个细化“字段定义 / 创建表单 / 专用编辑器”，提升字段级锁、在场提示和创建体验。
> 状态：进行中；hint 已完成字段/结构检查；validation 已完成字段/后端检查、创建表单/编辑器调整；task 已完成字段/后端检查；listener 已完成字段/后端检查；achievement 已完成字段/后端检查；account 已完成字段/后端检查；credit 已完成字段/后端检查、创建表单/编辑器调整；artifact 已完成字段/后端检查、创建表单/编辑器调整；artifact-node 已完成字段/后端检查、创建表单/编辑器调整；progress-node 已完成字段/后端检查、创建表单/编辑器调整；file-node 已完成字段/后端检查、创建表单/编辑器调整；asset 已完成字段/后端检查、创建表单/编辑器调整；code 已完成字段/后端检查、创建表单/编辑器调整；file-tree 已完成字段/后端检查、创建表单/编辑器调整；dag 已完成字段/后端检查、专用拓扑编辑器初版；script 已简化 namespace 为 `script`，注册表直接 fallback 到 FallbackEditor（编辑时锁定整个 state）；markdown 已增加 source namespace、分段 state 与专属 MarkdownEditor 初版，注册表分组独立为 `markdown`；questionnaire 已增加 source namespace、问卷 state 与专属 QuestionnaireEditor 初版。

## 推荐处理顺序

| 顺序 | 实体 kind | ui_kind | 当前编辑器 | 优先级理由 |
|---|---|---|---|---|
| 1 | `hint` | `form` | FormEditor | 字段最多、有 credit 引用关系，先做可复用的表单基础设施 |
| 2 | `validation` | `form` | FormEditor | 简单，验证 slug / handler_block_id 引用 |
| 3 | `task` | `form` | FormEditor | bitflag 依赖 + handler 引用，适合验证位标志编辑 |
| 4 | `listener` | `form` | FormEditor | 字段少，事件类型 + 优先级 + 依赖 |
| 5 | `achievement` | `form` | FormEditor | immediate/meta/condition/effect |
| 6 | `account` | `form` | FormEditor | 纯元数据，适合做简单表单 |
| 7 | `credit` | `form` | FormEditor | 最简单，可作为纯字段表单验收 |
| 8 | `artifact` | `form` | FormEditor | media_type + generator 引用 |
| 9 | `artifact-node` | `form` | FormEditor | 字段较多，有 display/access_rule/node_generator 引用 |
| 10 | `progress-node` | `dag-node` | FormEditor | 节点字段 + 后续 DAG 拓扑联动 |
| 11 | `file-node` | `form` | FormEditor | 节点字段 + 后续 file-tree 拓扑联动 |
| 12 | `file-tree` | `file-tree` | FileTreeEditor（专用拓扑编辑器） | 容器拓扑编辑器 |
| 13 | `dag` | `dag` | DagEditor（专用拓扑编辑器） | 容器拓扑编辑器 |
| 14 | `asset` | `asset` | FormEditor | 文件引用与上传替换 |
| 15 | `script` | `script` | FallbackEditor（注册表直接 fallback） | 脚本 JSON 编辑（整 state 锁） |
| 16 | `markdown` | `markdown` | MarkdownEditor | 分段 markdown 源文件编辑（注册表独立为 `markdown`） |
| 17 | `questionnaire` | `questionnaire` | QuestionnaireEditor | 问卷题目编辑（选择题/填空题，题目级锁） |
| 18 | `code` | `code` | CodeEditor | 代码块编辑 |

## 每个实体类型的通用 TODO 模板

- [ ] 校准 `@ellia/puzzle-schema` 中该 kind 的 `state` 类型/字段约束
- [ ] 在 `CreateEntityPanel` 中补充/校正该 kind 的默认 state 模板
- [ ] 实现/替换为专用编辑器组件，注册到 `registry.ts`
- [ ] 编辑器内按字段粒度加锁，展示字段级 presence
- [ ] 创建后自动打开或给出可操作反馈
- [ ] 补齐创建/编辑的错误提示与校验

## 分实体 TODO

### 1. hint

- [x] 字段：`stable_id`、`source_asset_id`、`download_name`、`display`、`credit_id`、`credit_amount`、`access_rule`（已对照 schema/后端校验）
  - 后端 `Hint(source, download_name, display, credit_id, credit_amount, access_rule)`：`source`（FileReference）与 `download_name` 均必填
  - 编辑器 `source_asset_id` 已改为必填；`download_name`、`display.title` 已改为必填；`credit_amount` 后端要求正整数
- [ ] 创建表单：自动建议 `hint:` 前缀，校验 credit_id 是否已注册
- [ ] 编辑器：结构化表单，`display` 容器字段锁，`credit_id` 下拉候选

### 2. validation

- [x] 字段：`stable_id`、`validation_id`、`handler_block_id`（已对照 schema/后端校验）
  - mythos 后端 `ValidationAttempt(stable_id, validation_id, handler)`：
    - `stable_id`：注册表内唯一；仅用于身份/去重，不参与 HTTP 路径
    - `validation_id`：公开 API slug，`POST /api/v1/validations/{validation_id}/attempts` 使用；后端规则 `^[a-z0-9][a-z0-9-]{0,63}$`，全局唯一
    - `handler`：异步 `(context: ValidationContext, payload) -> ValidationResult`；编辑器用 `handler_block_id` 引用 `code` 实体，导出时生成 handler
    - handler 可在事务内推进 progress、发放账号/资产、写 followups；`context.reject(reason, details)` → HTTP 409 Problem Details；返回 `accepted=false` 为 HTTP 200
  - 注意：前端 `VALIDATION_ID_RE`（`^[a-z0-9]+(?:-[a-z0-9]+)*$`）比后端严格，但缺少 64 字符上限；已对齐为 `^[a-zA-Z0-9_-]{1,64}$`
- [x] 创建表单：`validation_id` slug 校验（已对齐后端 regex + ≤64）
- [ ] 编辑器：结构化表单，handler 引用选择（引用 code 实体）

### 3. task

- [x] 字段：`task_id`、`dependencies`、`handler_block_id`（已对照 schema/后端校验）
  - mythos 后端 `TaskDefinition(task_id, handler, dependencies)`：
    - `task_id`：注册表内唯一；后端已放宽为 `^[^\s:]{1,128}$`（与编辑器 resource_id 的 id 部分一致）
    - `dependencies`：`PlayerInterfaces` 位掩码；编辑器用 `bitflag` 字段表示，`enums[i]` 对应位 `1 << i`（progress/artifacts/accounts/credits/hints/tasks/achievements）
    - `handler`：异步 `(context: TaskContext) -> None`；编辑器用 `handler_block_id` 引用 `code`（必填），导出时生成 handler
- [x] 创建表单：默认 `dependencies: 0`、`handler_block_id: ''`
- [x] 编辑器：bitflag 依赖位编辑（grid 勾选）+ handler 引用选择

### 4. listener

- [x] 字段：`event_type`、`priority`、`dependencies`、`listener_block_id`（已对照 schema/后端校验）
  - mythos 后端 `EventRegistry.on(event_type, priority=EventPriority)` + `EventContext` handler：
    - `event_type`：后端要求 Event 子类；编辑器使用 `player.constructed` / `player.deconstructing` / `account.login`，导出时映射
    - `priority`：后端 `EventPriority`（early/default/late = 100/200/300）；编辑器使用字符串 early/default/late，导出时映射
    - `dependencies`：`PlayerInterfaces` 位掩码；编辑器用 `bitflag` 字段表示
    - `listener`：异步 `(context: EventContext) -> None`；编辑器用 `listener_block_id` 引用 `code` 实体（必填），导出时生成 listener
- [x] 创建表单：默认 `event_type: player.constructed`、`priority: default`、`dependencies: 0`、`listener_block_id: ''`
- [x] 编辑器：事件类型/优先级下拉 + bitflag 依赖位编辑 + handler 引用选择

### 5. achievement

- [x] 字段：`achievement_id`、`immediate`、`meta`、`condition`、`effect`（已对照 schema/后端校验）
  - mythos 后端 `AchievementDefinition(stable_id, immediate, meta, condition, effect)`：
    - `achievement_id`：由 resource_id 提供，导出时映射 stable_id
    - `immediate`：默认 false；true 时达成后立即发放奖励，false 时需手动 claim
    - `meta`：成就元数据，title/description 等；编辑器使用 JSON CodeMirror 编辑
    - `condition`：可选，同步 `(player: Player) -> bool`
    - `effect`：必填，异步 `(player: Player) -> None`
- [x] 创建表单：默认 `immediate: false`、`meta: { title: "Example Achievement", description: "..." }`、`condition: ""`、`effect: ""`
- [x] 编辑器：meta JSON CodeMirror + condition/effect 引用选择
- [ ] 导出实现：暂不考虑，后续将 meta/condition/effect 映射到 `AchievementDefinition`

### 6. account

- [x] 字段：`account_id`、`display_name`、`permission`、`metadata`（已对照 schema/后端校验）
  - mythos 后端 `VirtualAccountTemplate(account_id, display_name, permission, metadata)`：
    - `account_id`：由 resource_id 提供，导出时映射
    - `display_name`：必填，非空字符串
    - `permission`：必填整数；编辑器已从 string 改为 number
    - `metadata`：JSON 对象，编辑器使用 JSON CodeMirror 编辑
- [x] 创建表单：默认 `permission: 0`、`metadata: {}`
- [x] 编辑器：metadata JSON CodeMirror 编辑

### 7. credit

- [x] 字段：`credit_id`、`display_name`、`metadata`
- [x] 创建表单：最简单默认模板
- [x] 编辑器：metadata JSON 编辑

### 8. artifact

- [x] 字段：`artifact_id`、`media_type`、`download_name`、`generator`
- [x] 创建表单：media_type 默认值
- [x] 编辑器：generator 引用选择

### 9. artifact-node

- [x] 字段：`stable_id`、`artifact`、`display`、`hidden`、`download_name`、`access_rule`、`node_generator`
- [x] 创建表单：display 子表单
- [x] 编辑器：引用字段较多，分组展示

### 10. progress-node

- [x] 字段：`how`、`mode`、`triggers_checkpoint`
- [x] 创建表单：how/mode 可选配置 + triggers_checkpoint
- [x] 编辑器：节点基础表单，后续与 dag 容器联动高亮

### 11. file-node

- [x] 字段：`stable_id`、`display`、`hidden`、`download_name`、`source_asset`、`access_rule`
- [x] 创建表单：directory/file 切换
- [x] 编辑器：FormEditor（已移除 FileTreeNodeEditor）

### 12. file-tree

- [x] 字段：`rootId`、`nodes`（扁平 FileTreeNode 表：id/name/isDirectory/inode/parent/order）
- [x] 创建表单：默认 `{ rootId: "root", nodes: { root: ... } }`
- [x] 编辑器：专用拓扑容器编辑（横向层级、节点卡片、添加/删除、下部信息面板）

### 13. dag

- [x] 字段：`entryIds`、`nodes`（扁平 DagNode 表：id/name/pnode/successors）
- [x] 创建表单：默认 `{ entryIds: [], nodes: {} }`
- [x] 编辑器：专用拓扑容器编辑（dagre 布局、孤立节点独立行、节点卡片、添加/编辑/删除、下部信息面板）

### 14. asset

- [x] 字段：`source_reference`、`file_reference`、`media_type`
- [x] 创建表单：可选择已有文件或先占位
- [x] 编辑器：文件预览、上传替换、引用展示

### 15. script

- [x] 字段：`stable_id`（deprecated，由 resource_id 提供）、`revision`、`body`、`access_rule`；namespace 已简化为 `script`
- [x] 创建表单：body 初始行（默认 `{ revision: 1, body: { kind: "script", lines: [] } }`）
- [x] 编辑器：注册表直接 fallback 到独立 FallbackEditor（CodeMirror JSON + M3 主题，右下角编辑/确认/取消，锁定整个 state）

### 16. markdown

- [x] 字段：`sort`（显式 UUID 顺序）、`segments`（UUID → { id, content }）
- [x] 创建表单：默认 `{ sort: [], segments: {} }`，namespace 为 `source`
- [x] 编辑器：专属 MarkdownEditor（纵向 flex + TransitionGroup 卡片、markdown-it 渲染、CodeMirror markdown 高亮、段级锁）
- [x] 注册表：`REGISTRY_OF_KIND.markdown` 独立为 `markdown`，不再与 files 共用

### 17. questionnaire

- [x] 字段：`description`（markdown 说明）、`sort`（显式 UUID 顺序）、`questions`（UUID → { id, type, description, data }）
- [x] 创建表单：默认 `{ description: "", sort: [], questions: {} }`，namespace 为 `source`
- [x] 编辑器：专属 QuestionnaireEditor（说明卡片 + TransitionGroup 题目卡片、markdown-it 渲染、CodeMirror markdown 编辑、题目级锁、选择题/填空题预览与编辑组件）
- [x] 注册表：`REGISTRY_OF_KIND.questionnaire` 独立为 `questionnaire`

### 18. code

- [x] 字段：`name`、`content`
- [x] 创建表单：默认 content 空
- [x] 编辑器：CodeMirror Python 编辑
