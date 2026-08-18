import type { EntityKind } from '@ellia/puzzle-schema'

import createTemplatesData from '../../../config/createTemplates.json'

export interface CreateTemplate {
  namespace: string
  fixed: {
    enable: boolean
    value: string
  }
  inject_id: {
    enable: boolean
    field: string
  }
  default: Record<string, unknown>
  comment: {
    description: string
    format: string
  }
}

export const CREATE_TEMPLATES = createTemplatesData as Record<EntityKind, CreateTemplate>
