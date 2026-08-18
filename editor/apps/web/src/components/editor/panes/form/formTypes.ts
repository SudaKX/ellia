export type FieldType = 'string' | 'bool' | 'number' | 'array' | 'object'

export interface FieldSpec {
  type: FieldType
  description: string
  hidden?: boolean
  optional?: boolean
  inner?: FormSpec
  namespace?: string
  item?: FieldSpec
  /** 引用实体时：保存实体 UUID 还是 resource_id 的 id 段 */
  valueMode?: 'entity_id' | 'id_part'
}

export type FormSpec = Record<string, FieldSpec>
