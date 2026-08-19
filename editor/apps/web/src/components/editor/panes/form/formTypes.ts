export type FieldType = 'string' | 'bool' | 'number' | 'array' | 'object'

export interface FieldSpec {
  type: FieldType
  description: string
  hidden?: boolean
  optional?: boolean
  inner?: FormSpec
  namespace?: string
  item?: FieldSpec
}

export type FormSpec = Record<string, FieldSpec>
