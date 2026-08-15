// @ellia/puzzle-schema — 核心数据类型（plan-v1.md §3.1）
// 11 个 Mythos 注册表的声明数据 TS 类型 + 编辑器实体模型。
// 实体是同步、版本号、补丁日志的基本单位；state 为权威当前状态。

import type { PythonSlot } from './python.js'

/** 实体 id（内部 UUID） */
export type EntityId = string
/** 全项目唯一的稳定 id（progress / file-tree / hint / script / validation / artifact-node 等） */
export type StableId = string

/** Mythos 全部 11 个注册表名（handoff.md §2.2） */
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

/** 实体种类（同步与版本的基本单位） */
export const ENTITY_KINDS = [
  'progress-node',
  'file-tree-node',
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
  'file-tree-node': 'files',
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

// ---------- 各实体 state ----------

/** file-tree.json manifest 的 display 字段 */
export interface DisplayField {
  label?: string
  description?: string
  icon?: string
  sort_order?: number
}

export type ProgressNodeKind = 'normal' | 'branch' | 'merge'

export interface ProgressNodeState {
  stable_id: StableId
  node_kind: ProgressNodeKind
  /** 后继节点 stable_id 列表（DAG 边） */
  successors: StableId[]
  is_entry: boolean
  triggers_checkpoint: boolean
}

export type FileTreeNodeKind = 'directory' | 'file'

export interface FileTreeNodeState {
  stable_id: StableId
  kind: FileTreeNodeKind
  name: string
  display: DisplayField
  hidden: boolean
  download_name?: string
  /** file 节点指向资产库中的 asset 实体 */
  source_asset_id?: EntityId
  /** access_rule 引用 python-block 实体（slot=access_rule） */
  access_rule_block_id?: EntityId
}

export interface AssetState {
  path: string
  media_type: string
  /** 文本资产内联存储；二进制资产存 entity_blobs 表（text 缺省） */
  text?: string
}

export interface HintDisplay {
  title?: string
  teaser?: string
  icon?: string
  sort_order?: number
}

export interface HintState {
  stable_id: StableId
  /** 来源资产（asset 实体引用） */
  source_asset_id?: EntityId
  download_name?: string
  display: HintDisplay
  /** 必须已注册的 credit_id（编辑器表单做即时提示） */
  credit_id: string
  credit_amount: number
  access_rule_block_id?: EntityId
}

/** 脚本 body 骨架；细节在 M2 对照 mythos Script 定义细化 */
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
  access_rule_block_id?: EntityId
}

export interface ValidationState {
  stable_id: StableId
  /** slug 格式（^[a-z0-9]+(?:-[a-z0-9]+)*$） */
  validation_id: string
  handler_block_id?: EntityId
}

export interface ArtifactTemplateState {
  artifact_id: string
  media_type: string
  download_name?: string
  generator_block_id?: EntityId
}

export interface ArtifactNodeState {
  stable_id: StableId
  path: string
  artifact_locator: string
  display: DisplayField
  hidden: boolean
  download_name?: string
  access_rule_block_id?: EntityId
  node_generator_block_id?: EntityId
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
  predicate_block_id?: EntityId
  reward_block_id?: EntityId
}

export interface TaskState {
  task_id: string
  dependencies: string[]
  handler_block_id?: EntityId
}

export interface EventListenerState {
  event_type: string
  priority: number
  dependencies: string[]
  listener_block_id?: EntityId
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

/** 实体（DB entities 行 + 同步载荷；version/state 即权威当前状态） */
export interface Entity<TKind extends EntityKind = EntityKind> {
  id: EntityId
  project_id: string
  kind: TKind
  /** 业务引用键（stable_id / account_id / credit_id…；python-block 为函数名） */
  ref: string
  version: number
  state: KindStateMap[TKind]
  /** tombstone：删除 = deleted 置 1 + 版本 +1，不物理删除 */
  deleted: boolean
  updated_at: string
}

/** 字段级变更：{field:{from,to}} 双向值（补丁日志/回滚用）| {field:value} 覆盖 */
export type Change = { from: unknown; to: unknown } | { value: unknown }

/** 补丁日志（entity_patches 表，每实体上限 N=100） */
export interface EntityPatch {
  id: number
  entity_id: EntityId
  base_version: number
  new_version: number
  changes: Record<string, Change>
  author_id: string
  created_at: string
}

/** 项目（projects 表） */
export interface Project {
  id: string
  /** 单一路径段（isValidModuleId 校验），全库唯一 */
  module_id: string
  display_name: string
  description: string
  /** 当前 mythos puzzles/__init__.py 内容（导出合并用，可为 null） */
  deploy_baseline: string | null
  created_by: string
  created_at: string
  updated_at: string
}
