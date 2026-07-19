import { markRaw, type Component } from 'vue'

import GlitchFilterDefs from '@/components/desktop/GlitchFilterDefs.vue'
import type { GlitchOptions } from '@/composables/useGlitchFilter'

export interface FilterOptionsByType {
  glitch: GlitchOptions
}

export type FilterType = keyof FilterOptionsByType
export type FilterOptions = FilterOptionsByType[FilterType]

export interface FilterRegistration {
  component: Component
}

export const filterRegistry: Record<FilterType, FilterRegistration> = {
  glitch: {
    component: markRaw(GlitchFilterDefs),
  },
}
