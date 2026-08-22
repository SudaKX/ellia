export type FieldType = 'string' | 'bool' | 'number' | 'array' | 'object' | 'bitflag' | 'json' | 'ref' | 'file'

export interface FieldOption {
  label: string
  value: string | number
}

export interface FieldSpec {
  type: FieldType
  description: string
  hidden?: boolean
  optional?: boolean
  inner?: FormSpec
  /** 仅 type=ref 时有效，且 type=ref 时必须提供 */
  namespace?: string
  item?: FieldSpec
  /** 仅 type=string 时有效：正则表达式字符串，用于编辑界面即时校验 */
  format?: string
  /** 仅 type=bitflag 时有效：按顺序列出每个枚举位，enums[i] 对应位 1 << i */
  enums?: string[]
  /** 仅 type=string/number 时有效：下拉候选选项 */
  options?: FieldOption[]
  /** 仅 type=string 时有效；优先级低于 options，提供推荐候选但允许自由输入 */
  recommends?: string[]
}

export type FormSpec = Record<string, FieldSpec>
