// @ellia/puzzle-schema — Python 代码块模型（plan-v1.md §3.2）
// 用户在编辑器中直接编写 Python 函数体；导出器负责加 @_handler 装饰器与 imports。

/** Python 代码块 slot：决定签名模板与宿主引用方式 */
export const PYTHON_SLOTS = [
  'access_rule',
  'validation_handler',
  'artifact_generator',
  'node_generator',
  'achievement_predicate',
  'achievement_reward',
  'task_handler',
  'event_listener',
  'free',
] as const

export type PythonSlot = (typeof PYTHON_SLOTS)[number]

/** 各 slot 的函数签名模板（{name} 为代码块名占位符） */
export const SLOT_SIGNATURES: Record<PythonSlot, string> = {
  access_rule: 'def {name}(player: Player) -> bool',
  validation_handler: 'async def {name}(context: ValidationContext, payload) -> ValidationResult',
  artifact_generator: 'async def {name}(player: Player) -> RawArtifact',
  node_generator: 'async def {name}(player, meta, node: ArtifactNode) -> ArtifactNode',
  achievement_predicate: 'def {name}(player: Player) -> bool',
  achievement_reward: 'async def {name}(player: Player) -> None',
  task_handler: 'async def {name}(context: TaskContext) -> None',
  event_listener: 'async def {name}(context: EventContext) -> None',
  free: '# 任意模块级函数',
}

/** Python 函数名规则（与 Python 标识符一致） */
export const PYTHON_NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/

export function isPythonName(name: string): boolean {
  return PYTHON_NAME_RE.test(name)
}

/** 生成 slot 对应的签名模板文本 */
export function signatureTemplate(slot: PythonSlot, name: string): string {
  return SLOT_SIGNATURES[slot].replace('{name}', name)
}
