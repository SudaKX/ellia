// @ellia/puzzle-schema — 核心数据类型（plan-v2 §3）
// 16 种实体 kind 的声明数据 TS 类型 + 编辑器实体模型。
// 实体是同步、版本号、历史快照的基本单位；state 为权威当前状态。



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
  'file-node',
  'file-tree',
  'dag',
  'asset',
  'hint',
  'script',
  'validation',
  'artifact',
  'artifact-node',
  'account',
  'credit',
  'achievement',
  'task',
  'listener',
  'code',
] as const

export type EntityKind = (typeof ENTITY_KINDS)[number]

/** kind → 注册表 映射（实体树分组用）；code 是代码实体，不属于任何注册表 */
export const REGISTRY_OF_KIND: Record<EntityKind, RegistryName | 'code'> = {
  'progress-node': 'progress',
  'dag': 'progress',
  'file-node': 'files',
  'file-tree': 'files',
  asset: 'files',
  hint: 'hints',
  script: 'scripts',
  validation: 'validations',
  artifact: 'artifacts',
  'artifact-node': 'artifacts',
  account: 'accounts',
  credit: 'credits',
  achievement: 'achievements',
  task: 'tasks',
  listener: 'events',
  code: 'code',
}

/** 前端展示类型（ui_kind）：决定前端用哪个组件渲染该实体 */
export const UI_KINDS = [
  'dag-node',
  'file-tree',
  'dag',
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
  'asset',
  'artifact',
  'inode',
  'pnode',
  'source',
  'account',
  'credit',
  'achievement',
  'validation',
  'task',
  'listener',
  'code',
  'file-tree',
  'dag',
] as const

export type ResourceNamespace = (typeof RESOURCE_NAMESPACES)[number]

/** kind → 前端展示类型（第一版一对一映射） */
const UI_KIND_OF_KIND: Record<EntityKind, UiKind> = {
  'progress-node': 'dag-node',
  'file-node': 'form',
  'file-tree': 'file-tree',
  'dag': 'dag',
  asset: 'asset',
  hint: 'form',
  script: 'script',
  validation: 'form',
  artifact: 'form',
  'artifact-node': 'form',
  account: 'form',
  credit: 'form',
  achievement: 'form',
  task: 'form',
  listener: 'form',
  code: 'code',
}

/** kind → resource_id 命名空间 */
const NAMESPACE_OF_KIND: Record<EntityKind, ResourceNamespace> = {
  'progress-node': 'pnode',
  'file-node': 'inode',
  hint: 'hint',
  script: 'stable-id',
  validation: 'validation',
  'artifact-node': 'inode',
  asset: 'asset',
  artifact: 'artifact',
  account: 'account',
  credit: 'credit',
  achievement: 'achievement',
  task: 'task',
  listener: 'listener',
  code: 'code',
  'file-tree': 'file-tree',
  'dag': 'dag',
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

export type ProgressNodeMode = 'and' | 'or'

/** 进度节点：纯节点数据，拓扑在 dag 容器中 */
export interface ProgressNodeState {
  /** branch 目标选择 code 实体（entity id）；可选，导出器决定如何使用 */
  how?: EntityId
  /** merge 合并模式；可选，导出器决定如何使用 */
  mode?: ProgressNodeMode
  triggers_checkpoint: boolean
}

/** 文件树节点：纯静态节点数据，父子拓扑在 file-tree 容器中 */
export interface FileTreeNodeState {
  /** @deprecated 由 resource_id 提供，导出时解析 */
  stable_id?: StableId
  display: DisplayField
  hidden: boolean
  download_name?: string
  /** file 节点指向资产库中的 asset 实体（entity id） */
  source_asset?: EntityId
  /** access_rule 引用 code 实体（entity id） */
  access_rule?: EntityId
}

/** file-tree 内部节点：独立于 file-node 实体，id 是树内 UUID */
export interface FileTreeNode {
  /** 树节点 UUID；根节点固定为 "root" */
  id: string
  /** 规范路径段，如 "assets"；根节点为 "/" */
  name: string
  /** 是否为文件夹；文件夹不附加 inode，文件必须附加 inode */
  isDirectory: boolean
  /** 链接到 inode:xxx 的 file-node/artifact-node 实体 id；文件夹为 null，文件必填 */
  inode: EntityId | null
  /** 父节点 id；根节点为 null */
  parent: string | null
  /** 同级排序，运行时按 order 升序 */
  order: number
}

/** 文件树容器：扁平节点表，直接以 TreeNodeId 寻址 */
export interface FileTreeState {
  rootId: string
  /** TreeNodeId → FileTreeNode */
  nodes: Record<string, FileTreeNode>
}

/** DAG 内部节点：独立于 progress-node 实体，id 是图内 UUID */
export interface DagNode {
  /** 图节点 UUID */
  id: string
  /** 可读名称，必填 */
  name: string
  /** 链接到 pnode:xxx 的 progress-node 实体 id；可为空 */
  pnode: EntityId | null
  /** 后继图节点 id 列表（有序） */
  successors: string[]
}

/** DAG 容器：扁平节点表，直接以 DagNodeId 寻址 */
export interface DagState {
  entryIds: string[]
  /** DagNodeId → DagNode */
  nodes: Record<string, DagNode>
}

/** 资产：文件引用 + 可选的 source 引用；命名空间为 asset */
export interface AssetState {
  /** source 引用（后续使用；可选） */
  source_reference?: EntityId
  /** 指向 files 表（UUID）；可选，与 source_reference 至少填一个 */
  file_reference?: string
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
  /** @deprecated 由 resource_id 提供，导出时解析 */
  stable_id?: StableId
  /** 来源资产实体（entity id）；mythos Hint.source 为 FileReference，导出时必需 */
  source_asset_id: EntityId
  /** mythos Hint.download_name 必填：安全单路径段 */
  download_name: string
  display: HintDisplay
  /** 必须已注册的 credit 实体（entity id） */
  credit_id: EntityId
  credit_amount: number
  /** 访问规则 code 实体（entity id） */
  access_rule?: EntityId
}

/** 脚本 body 骨架；细节后续对照 mythos Script 定义细化 */
export interface ScriptBody {
  kind: string
  lines: string[]
  input?: string
  validation_id?: string
}

export interface ScriptState {
  /** @deprecated 由 resource_id 提供，导出时解析 */
  stable_id?: StableId
  revision: number
  body: ScriptBody
  /** 访问规则 code 实体（entity id） */
  access_rule?: EntityId
}

export interface ValidationState {
  /** @deprecated 由 resource_id 提供，导出时解析 */
  stable_id?: StableId
  /** 公开 API slug（^[a-zA-Z0-9_-]{1,64}$） */
  validation_id: string
  /** 校验处理 code 实体（entity id） */
  handler_block_id?: EntityId
}

export interface ArtifactTemplateState {
  /** @deprecated 由 resource_id 提供，导出时解析 */
  artifact_id?: string
  media_type: string
  download_name?: string
  /** 生成器 code 实体（entity id） */
  generator?: EntityId
}

export interface ArtifactNodeState {
  /** @deprecated 由 resource_id 提供，导出时解析 */
  stable_id?: StableId
  /** 所属 artifact 实体（entity id） */
  artifact: EntityId
  display: DisplayField
  hidden: boolean
  download_name?: string
  /** 访问规则 code 实体（entity id） */
  access_rule?: EntityId
  /** 节点生成器 code 实体（entity id） */
  node_generator: EntityId
}

export interface AccountTemplateState {
  /** @deprecated 由 resource_id 提供，导出时解析 */
  account_id?: string
  display_name: string
  permission: number
  metadata: Record<string, unknown>
}

export interface CreditTemplateState {
  /** @deprecated 由 resource_id 提供，导出时解析 */
  credit_id?: string
  display_name: string
  metadata: Record<string, unknown>
}

export interface AchievementState {
  /** @deprecated 由 resource_id 提供，导出时解析 */
  achievement_id?: string
  /** 是否达成后立即发放奖励；默认 false */
  immediate: boolean
  /** 成就元数据，例如 title / description */
  meta: Record<string, unknown>
  /** 成就判定 code 实体（entity id），可选 */
  condition?: EntityId
  /** 成就奖励 code 实体（entity id），必填 */
  effect: EntityId
}

export interface TaskState {
  /** @deprecated 由 resource_id 提供，导出时解析 */
  task_id?: string
  /** PlayerInterfaces 位掩码；第 i 位对应 formSpecs enums[i] */
  dependencies: number
  /** 任务处理 code 实体（entity id） */
  handler_block_id: EntityId
}

export const EVENT_LISTENER_TYPES = [
  { value: 'player.constructed', label: 'PlayerConstructedEvent' },
  { value: 'player.deconstructing', label: 'PlayerDeconstructingEvent' },
  { value: 'account.login', label: 'VirtualAccountLoggedInEvent' },
] as const

export type EventListenerType = (typeof EVENT_LISTENER_TYPES)[number]['value']

export const EVENT_LISTENER_PRIORITIES = [
  { value: 'early', label: 'early' },
  { value: 'default', label: 'default' },
  { value: 'late', label: 'late' },
] as const

export type EventListenerPriority = (typeof EVENT_LISTENER_PRIORITIES)[number]['value']

export interface EventListenerState {
  event_type: EventListenerType
  priority: EventListenerPriority
  /** PlayerInterfaces 位掩码；第 i 位对应 formSpecs enums[i] */
  dependencies: number
  /** 事件监听 code 实体（entity id） */
  listener_block_id: EntityId
}

/** 代码块（独立实体，content 为 Python 源码） */
export interface CodeBlockState {
  /** @deprecated 由 resource_id 提供，导出时解析 */
  name?: string
  /** 用户编写的函数体源码 */
  content: string
}

/** 任意 kind 的 state 联合 */
export type EntityState =
  | ProgressNodeState
  | FileTreeNodeState
  | FileTreeState
  | DagState
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
  | CodeBlockState

/** kind → state 的精确映射（强类型同步层用） */
export interface KindStateMap {
  'progress-node': ProgressNodeState
  'file-node': FileTreeNodeState
  'file-tree': FileTreeState
  'dag': DagState
  asset: AssetState
  hint: HintState
  script: ScriptState
  validation: ValidationState
  'artifact': ArtifactTemplateState
  'artifact-node': ArtifactNodeState
  account: AccountTemplateState
  'credit': CreditTemplateState
  achievement: AchievementState
  task: TaskState
  listener: EventListenerState
  code: CodeBlockState
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
  /** 实体注释；可选以兼容旧缓存数据（缺省视为空字符串） */
  comment?: string
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
  /** 实体注释；可选以兼容旧缓存数据（缺省视为空字符串） */
  comment?: string
}

/** 实体历史快照（entity_history 行；state 列存 {group, resource_id, comment, state}） */
export interface EntityHistoryEntry {
  version: number
  group: string
  resource_id: string
  comment: string
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
  module: string | null
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
  module: string | null
  size: number
  sha256: string
  uploaded_by: string
  created_at: string
}

export interface FileListResponse {
  files: ApiFileRecord[]
}
