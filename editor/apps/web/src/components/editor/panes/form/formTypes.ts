export type FieldType = 'string' | 'bool' | 'number' | 'array' | 'object'

export interface FieldSpec {
  type: FieldType
  description: string
  hidden?: boolean
  optional?: boolean
  inner?: FormSpec
  namespace?: string
  item?: FieldSpec
  /** 仅 type=string 时有效：正则表达式字符串，用于编辑界面即时校验 */
  format?: string
}

export type FormSpec = Record<string, FieldSpec>
