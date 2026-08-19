# 实体编辑器细化 TODO

> 目标：按实体类型逐个细化“字段定义 / 创建表单 / 专用编辑器”，提升字段级锁、在场提示和创建体验。
> 状态：进行中；hint 已完成字段/结构检查；validation 字段/后端检查已完成，按顺序继续创建表单与编辑器。

## 推荐处理顺序

| 顺序 | 实体 kind | ui_kind | 当前编辑器 | 优先级理由 |
|---|---|---|---|---|
| 1 | `hint` | `form` | FormEditor | 字段最多、有 credit 引用关系，先做可复用的表单基础设施 |
| 2 | `validation` | `form` | FormEditor | 简单，验证 slug / handler_block_id 引用 |
| 3 | `task` | `form` | FormEditor | 依赖列表简单，适合作为列表字段编辑器样板 |
| 4 | `event-listener` | `form` | FormEditor | 字段少，事件类型 + 优先级 + 依赖 |
| 5 | `achievement` | `form` | FormEditor | 有 secret/display/predicate/reward 引用 |
| 6 | `account-template` | `form` | FormEditor | 纯元数据，适合做简单表单 |
| 7 | `credit-template` | `form` | FormEditor | 最简单，可作为纯字段表单验收 |
| 8 | `artifact-template` | `form` | FormEditor | media_type + generator 引用 |
| 9 | `artifact-node` | `form` | FormEditor | 字段较多，有 display/access_rule/node_generator 引用 |
| 10 | `progress-node` | `dag-node` | ProgressNodeEditor（FormEditor 封装） | 节点字段 + 后续 DAG 拓扑联动 |
| 11 | `file-tree-node` | `tree-node` | FileTreeNodeEditor（FormEditor 封装） | 节点字段 + 后续 file-tree 拓扑联动 |
| 12 | `file-tree` | `file-tree` | FileTreeEditor（FormEditor 封装） | 容器拓扑编辑器 |
| 13 | `progress-dag` | `progress-dag` | ProgressDagEditor（FormEditor 封装） | 容器拓扑编辑器 |
| 14 | `asset` | `asset` | AssetEditor | 文件引用与上传替换 |
| 15 | `script` | `script` | ScriptEditor | 脚本行编辑 |
| 16 | `python-block` | `code` | CodeEditor | 代码块编辑 |

## 每个实体类型的通用 TODO 模板

- [ ] 校准 `@ellia/puzzle-schema` 中该 kind 的 `state` 类型/字段约束
- [ ] 在 `CreateEntityPanel` 中补充/校正该 kind 的默认 state 模板
- [ ] 实现/替换为专用编辑器组件，注册到 `registry.ts`
- [ ] 编辑器内按字段粒度加锁，展示字段级 presence
- [ ] 创建后自动打开或给出可操作反馈
- [ ] 补齐创建/编辑的错误提示与校验

## 分实体 TODO

### 1. hint

- [x] 字段：`stable_id`、`source_asset_id`、`download_name`、`display`、`credit_id`、`credit_amount`、`access_rule_block_id`（已对照 schema/后端校验）
  - 后端 `Hint(source, download_name, display, credit_id, credit_amount, access_rule)`：`source`（FileReference）与 `download_name` 均必填
  - 编辑器 `source_asset_id` 已改为必填；`download_name`、`display.title` 已改为必填；`credit_amount` 后端要求正整数
- [ ] 创建表单：自动建议 `hint:` 前缀，校验 credit_id 是否已注册
- [ ] 编辑器：结构化表单，`display` 容器字段锁，`credit_id` 下拉候选

### 2. validation

- [x] 字段：`stable_id`、`validation_id`、`handler_block_id`（已对照 schema/后端校验）
  - mythos 后端 `ValidationAttempt(stable_id, validation_id, handler)`：
    - `stable_id`：注册表内唯一；仅用于身份/去重，不参与 HTTP 路径
    - `validation_id`：公开 API slug，`POST /api/v1/validations/{validation_id}/attempts` 使用；后端规则 `^[a-z0-9][a-z0-9-]{0,63}$`，全局唯一
    - `handler`：异步 `(context: ValidationContext, payload) -> ValidationResult`；编辑器用 `handler_block_id` 引用 `python-block`（slot=`validation_handler`），导出时生成 handler
    - handler 可在事务内推进 progress、发放账号/资产、写 followups；`context.reject(reason, details)` → HTTP 409 Problem Details；返回 `accepted=false` 为 HTTP 200
  - 注意：前端 `VALIDATION_ID_RE`（`^[a-z0-9]+(?:-[a-z0-9]+)*$`）比后端严格，但缺少 64 字符上限；建议对齐后端
- [ ] 创建表单：`validation_id` slug 校验（对齐后端 regex + ≤64；默认 `handler_block_id` 可选）
- [ ] 编辑器：结构化表单，handler 引用选择（仅列出 `slot='validation_handler'` 的 python-block）

### 3. task

- [ ] 字段：`task_id`、`dependencies`、`handler_block_id`
- [ ] 创建表单：默认 `dependencies: []`
- [ ] 编辑器：数组字段编辑（增删依赖项）

### 4. event-listener

- [ ] 字段：`event_type`、`priority`、`dependencies`、`listener_block_id`
- [ ] 创建表单：自动建议 `listener-id:` 前缀
- [ ] 编辑器：事件类型输入 + 依赖数组编辑

### 5. achievement

- [ ] 字段：`achievement_id`、`secret`、`display`、`predicate_block_id`、`reward_block_id`
- [ ] 创建表单：secret 开关、display 子表单
- [ ] 编辑器：display 字段容器锁、block 引用选择

### 6. account-template

- [ ] 字段：`account_id`、`display_name`、`permission`、`metadata`
- [ ] 创建表单：metadata JSON 编辑
- [ ] 编辑器：metadata 独立容器锁

### 7. credit-template

- [ ] 字段：`credit_id`、`display_name`、`metadata`
- [ ] 创建表单：最简单默认模板
- [ ] 编辑器：metadata JSON 编辑

### 8. artifact-template

- [ ] 字段：`artifact_id`、`media_type`、`download_name`、`generator_block_id`
- [ ] 创建表单：media_type 默认值
- [ ] 编辑器：generator 引用选择

### 9. artifact-node

- [ ] 字段：`stable_id`、`path`、`artifact_locator`、`display`、`hidden`、`download_name`、`access_rule_block_id`、`node_generator_block_id`
- [ ] 创建表单：path/display 子表单
- [ ] 编辑器：引用字段较多，分组展示

### 10. progress-node

- [ ] 字段：`stable_id`、`node_kind`、`triggers_checkpoint`
- [ ] 创建表单：node_kind 下拉（normal/branch/merge）
- [ ] 编辑器：节点基础表单，后续与 progress-dag 联动高亮

### 11. file-tree-node

- [ ] 字段：`stable_id`、`kind`、`name`、`display`、`hidden`、`download_name`、`source_asset_id`、`access_rule_block_id`
- [ ] 创建表单：directory/file 切换
- [ ] 编辑器：文件树节点表单，后续与 file-tree 联动

### 12. file-tree

- [ ] 字段：`root_stable_id`、`children`
- [ ] 创建表单：默认 `{ root_stable_id: null, children: {} }`
- [ ] 编辑器：拓扑容器编辑（根节点、父子排序）

### 13. progress-dag

- [ ] 字段：`entry_stable_ids`、`successors`
- [ ] 创建表单：默认 `{ entry_stable_ids: [], successors: {} }`
- [ ] 编辑器：DAG 入口/边编辑

### 14. asset

- [ ] 字段：`file_id`、`media_type`
- [ ] 创建表单：可选择已有文件或先占位
- [ ] 编辑器：文件预览、上传替换、引用展示

### 15. script

- [ ] 字段：`stable_id`、`revision`、`body`、`access_rule_block_id`
- [ ] 创建表单：body 初始行
- [ ] 编辑器：CodeMirror 行编辑 + revision 展示

### 16. python-block

- [ ] 字段：`name`、`slot`、`content`
- [ ] 创建表单：slot 下拉（access_rule/validation_handler/...）
- [ ] 编辑器：CodeMirror Python 编辑 + slot 签名提示
