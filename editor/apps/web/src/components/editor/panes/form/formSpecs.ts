import type { EntityKind } from '@ellia/puzzle-schema'

import formSpecsData from '../../../../config/formSpecs.json'
import type { FormSpec } from './formTypes'

/** form 编辑器渲染数据；编辑时直接改 config/formSpecs.json（与 createTemplates.json 同方式）。 */
export const FORM_SPECS = formSpecsData as Partial<Record<EntityKind, FormSpec>>
