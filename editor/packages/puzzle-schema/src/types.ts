// @ellia/puzzle-schema — 核心数据类型（plan-v2 §3）
// 16 种实体 kind 的声明数据 TS 类型 + 编辑器实体模型。
// 实体是同步、版本号、历史快照的基本单位；state 为权威当前状态。

import type { PythonSlot } from './python.js'

/** 实体 id（内部 UUID） */
export type EntityId = string
/** 项目内唯一的稳定 id（节点、hint、script、validation、artifact-node 等） */
export type StableId = string

/** Mythos 全部 11 个注册表名 */
export const REGISTRY_NAMES = [
  'files',
  'progress',
  'scripts',
  'validations',
  'artifacts',
  'accounts',
  'credits',
  'hints',
  'events',
  'tasks',
  'achievements',
] as const

export type RegistryName = (typeof REGISTRY_NAMES)[number]

/** 实体种类（同步与版本的基本单位）；节点与拓扑分离，容器承载结构 */
export const ENTITY_KINDS = [
  'progress-node',
  'file-tree-node',
  'file-tree',
  'progress-dag',
  'asset',
  'hint',
  'script',
  'validation',
  'artifact-template',
  'artifact-node',
  'account-template',
  'credit-template',
  'achievement',
  'task',
  'event-listener',
  'python-block',
] as const

export type EntityKind = (typeof ENTITY_KINDS)[number]

/** kind → 注册表 映射（实体树分组用）；python-block 是代码实体，不属于任何注册表 */
export const REGISTRY_OF_KIND: Record<EntityKind, RegistryName | 'code'> = {
  'progress-node': 'progress',
  'progress-dag': 'progress',
  'file-tree-node': 'files',
  'file-tree': 'files',
  asset: 'files',
  hint: 'hints',
  script: 'scripts',
  validation: 'validations',
  'artifact-template': 'artifacts',
  'artifact-node': 'artifacts',
  'account-template': 'accounts',
  'credit-template': 'credits',
  achievement: 'achievements',
  task: 'tasks',
  'event-listener': 'events',
  'python-block': 'code',
}

/** 前端展示类型（ui_kind）：决定前端用哪个组件渲染该实体 */
export const UI_KINDS = [
  'dag-node',
  'tree-node',
  'file-tree',
  'progress-dag',
  'asset',
  'script',
  'code',
  'form',
] as const

export type UiKind = (typeof UI_KINDS)[number]

/** resource_id 的命名空间（内嵌在 resource_id 前缀中，不单独建列） */
export const RESOURCE_NAMESPACES = [
  'stable-id',
  'hint',
  'asset-path',
  'artifact-id',
  'account-id',
  'credit-id',
  'achievement-id',
  'task-id',
  'listener-id',
  'python-name',
  'file-tree',
  'progress-dag',
] as const

export type ResourceNamespace = (typeof RESOURCE_NAMESPACES)[number]

/** kind → 前端展示类型（第一版一对一映射） */
const UI_KIND_OF_KIND: Record<EntityKind, UiKind> = {
  'progress-node': 'dag-node',
  'file-tree-node': 'tree-node',
  'file-tree': 'file-tree',
  'progress-dag': 'progress-dag',
  asset: 'asset',
  hint: 'form',
  script: 'script',
  validation: 'form',
  'artifact-template': 'form',
  'artifact-node': 'form',
  'account-template': 'form',
  'credit-template': 'form',
  achievement: 'form',
  task: 'form',
  'event-listener': 'form',
  'python-block': 'code',
}

/** kind → resource_id 命名空间 */
const NAMESPACE_OF_KIND: Record<EntityKind, ResourceNamespace> = {
  'progress-node': 'stable-id',
  'file-tree-node': 'stable-id',
  hint: 'hint',
  script: 'stable-id',
  validation: 'stable-id',
  'artifact-node': 'stable-id',
  asset: 'asset-path',
  'artifact-template': 'artifact-id',
  'account-template': 'account-id',
  'credit-template': 'credit-id',
  achievement: 'achievement-id',
  task: 'task-id',
  'event-listener': 'listener-id',
  'python-block': 'python-name',
  'file-tree': 'file-tree',
  'progress-dag': 'progress-dag',
}

export function uiKindFor(kind: EntityKind): UiKind {
  return UI_KIND_OF_KIND[kind]
}

export function namespaceFor(kind: EntityKind): ResourceNamespace {
  return NAMESPACE_OF_KIND[kind]
}

// ---------- 各实体 state ----------

/** file-tree.json manifest 的 display 字段 */
export interface DisplayField {
  label?: string
  description?: string
  icon?: string
  sort_order?: number
}

export type ProgressNodeKind = 'normal' | 'branch' | 'merge'

/** 进度节点：纯节点数据，拓扑在 progress-dag 容器中 */
export interface ProgressNodeState {
  stable_id: StableId
  node_kind: ProgressNodeKind
  triggers_checkpoint: boolean
}

export type FileTreeNodeKind = 'directory' | 'file'

/** 文件树节点：纯节点数据，父子拓扑在 file-tree 容器中 */
export interface FileTreeNodeState {
  stable_id: StableId
  kind: FileTreeNodeKind
  name: string
  display: DisplayField
  hidden: boolean
  download_name?: string
  /** file 节点指向资产库中的 asset 实体 resource_id（asset-path:…） */
  source_asset_id?: string
  /** access_rule 引用 python-block 实体 resource_id（python-name:…） */
  access_rule_block_id?: string
}

/** 文件树容器：持有整棵树拓扑与排序；节点只按 stable_id 引用 */
export interface FileTreeState {
  root_stable_id: StableId | null
  /** parent stable_id → 有序 child stable_id 列表 */
  children: Record<StableId, StableId[]>
}

/** 进度 DAG 容器：持有全部拓扑与入口；节点只按 stable_id 引用 */
export interface ProgressDagState {
  entry_stable_ids: StableId[]
  /** from stable_id → 有序 to stable_id 列表 */
  successors: Record<StableId, StableId[]>
}

/** 资产：file-reference 已并入 asset；路径身份由 resource_id（asset-path:<相对路径>）承载 */
export interface AssetState {
  /** 指向 files 表（UUID）；允许悬空 */
  file_id: string
  /** 与 mythos FileReference.media_type 对齐 */
  media_type: string
}

export interface HintDisplay {
  /** mythos HintDisplayParams.title 必填：非空单行 */
  title: string
  teaser?: string
  icon?: string
  sort_order?: number
}

export interface HintState {
  stable_id: StableId
  /** 来源资产 resource_id（asset-path:…）；mythos Hint.source 为 FileReference，导出时必需 */
  source_asset_id: string
  /** mythos Hint.download_name 必填：安全单路径段 */
  download_name: string
  display: HintDisplay
  /** 必须已注册的 credit-template resource_id（credit-id:…；编辑器表单做即时提示） */
  credit_id: string
  credit_amount: number
  /** 访问规则 python-block resource_id（python-name:…） */
  access_rule_block_id?: string
}

/** 脚本 body 骨架；细节后续对照 mythos Script 定义细化 */
export interface ScriptBody {
  kind: string
  lines: string[]
  input?: string
  validation_id?: string
}

export interface ScriptState {
  stable_id: StableId
  revision: number
  body: ScriptBody
  /** 访问规则 python-block resource_id（python-name:…） */
  access_rule_block_id?: string
}

export interface ValidationState {
  stable_id: StableId
  /** slug 格式（^[a-z0-9]+(?:-[a-z0-9]+)*$） */
  validation_id: string
  /** 校验处理 python-block resource_id（python-name:…） */
  handler_block_id?: string
}

export interface ArtifactTemplateState {
  artifact_id: string
  media_type: string
  download_name?: string
  /** 生成器 python-block resource_id（python-name:…） */
  generator_block_id?: string
}

export interface ArtifactNodeState {
  stable_id: StableId
  path: string
  artifact_locator: string
  display: DisplayField
  hidden: boolean
  download_name?: string
  /** 访问规则 python-block resource_id（python-name:…） */
  access_rule_block_id?: string
  /** 节点生成器 python-block resource_id（python-name:…） */
  node_generator_block_id?: string
}

export interface AccountTemplateState {
  account_id: string
  display_name: string
  permission: string
  metadata: Record<string, unknown>
}

export interface CreditTemplateState {
  credit_id: string
  display_name: string
  metadata: Record<string, unknown>
}

export interface AchievementDisplay {
  title: string
  description?: string
}

export interface AchievementState {
  achievement_id: string
  secret: boolean
  display: AchievementDisplay
  /** 成就判定 python-block resource_id（python-name:…） */
  predicate_block_id?: string
  /** 成就奖励 python-block resource_id（python-name:…） */
  reward_block_id?: string
}

export interface TaskState {
  task_id: string
  dependencies: string[]
  /** 任务处理 python-block resource_id（python-name:…） */
  handler_block_id?: string
}

export interface EventListenerState {
  event_type: string
  priority: number
  dependencies: string[]
  /** 事件监听 python-block resource_id（python-name:…） */
  listener_block_id?: string
}

/** python 代码块（独立实体，slot 决定签名模板，见 python.ts） */
export interface PythonBlockState {
  /** 函数名（isPythonName 校验） */
  name: string
  slot: PythonSlot
  /** 用户编写的函数体源码 */
  content: string
}

/** 任意 kind 的 state 联合 */
export type EntityState =
  | ProgressNodeState
  | FileTreeNodeState
  | FileTreeState
  | ProgressDagState
  | AssetState
  | HintState
  | ScriptState
  | ValidationState
  | ArtifactTemplateState
  | ArtifactNodeState
  | AccountTemplateState
  | CreditTemplateState
  | AchievementState
  | TaskState
  | EventListenerState
  | PythonBlockState

/** kind → state 的精确映射（强类型同步层用） */
export interface KindStateMap {
  'progress-node': ProgressNodeState
  'file-tree-node': FileTreeNodeState
  'file-tree': FileTreeState
  'progress-dag': ProgressDagState
  asset: AssetState
  hint: HintState
  script: ScriptState
  validation: ValidationState
  'artifact-template': ArtifactTemplateState
  'artifact-node': ArtifactNodeState
  'account-template': AccountTemplateState
  'credit-template': CreditTemplateState
  achievement: AchievementState
  task: TaskState
  'event-listener': EventListenerState
  'python-block': PythonBlockState
}

/** 实体（DB entities 行；revision 为同步锚点，version 为谱系指针） */
export interface Entity<TKind extends EntityKind = EntityKind> {
  id: EntityId
  project_id: string
  group: string
  kind: TKind
  ui_kind: UiKind
  resource_id: string
  revision: number
  version: number
  state: KindStateMap[TKind]
  created_at: string
  updated_at: string
}

/** 同步载荷（join/sync/created 用；不含 project_id，客户端按房间上下文归属） */
export interface EntityRecord<TKind extends EntityKind = EntityKind> {
  id: EntityId
  group: string
  kind: TKind
  ui_kind: UiKind
  resource_id: string
  revision: number
  version: number
  state: KindStateMap[TKind]
}

/** 实体历史快照（entity_history 行） */
export interface EntityHistoryEntry {
  version: number
  state: EntityState
  author_id: string
  created_at: string
}

/** 项目（projects 表） */
export interface Project {
  id: string
  /** 单一路径段（isValidModuleId 校验），全库唯一 */
  module_id: string
  display_name: string
  description: string | null
  /** 当前 mythos puzzles/__init__.py 内容（导出合并用，可为 null） */
  deploy_baseline: string | null
  created_by: string
  created_at: string
  updated_at: string
}

/** 文件元数据（files 表行） */
export interface FileRecord {
  id: string
  original_name: string | null
  media_type: string
  size: number
  sha256: string
  uploaded_by: string
  created_at: string
}

/** 文件列表响应（API 使用 file_id 作为对外字段名） */
export interface ApiFileRecord {
  file_id: string
  original_name: string | null
  media_type: string
  size: number
  sha256: string
  uploaded_by: string
  created_at: string
}

export interface FileListResponse {
  files: ApiFileRecord[]
}
