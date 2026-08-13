/**
 * # 滤镜注册表
 *
 * FilterHost 组件通过此注册表查找滤镜类型对应的 Vue 组件并动态渲染。
 * 目前仅注册了 `glitch` 一种滤镜类型，后续可扩展其他视觉效果。
 *
 * ## 扩展方式
 *
 * 1. 在 `FilterOptionsByType` 中添加新类型及其配置接口
 * 2. 在 `filterRegistry` 中注册对应的组件
 * 3. 各组件的 `filters` 字段即可引用新类型
 */

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
