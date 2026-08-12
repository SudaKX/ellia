/**
 * # useTheme — 出题器多主题（与 desktop 的 useTheme 同机制，独立存储）
 *
 * 基于 `<html data-theme="xxx">` 属性 + CSS 变量覆盖（styles/main.css），
 * 切换实时生效（无需刷新），选择持久化到 localStorage（key: ellia.question.theme）。
 *
 * 不经过 Pinia：主题是全局副作用，模块级函数即可，UI 组件自行维护当前值。
 *
 * @example
 * ```ts
 * import { THEMES, currentTheme, setTheme } from '@/composables/useTheme'
 * // 启动时（main.ts）：applyInitialTheme()
 * // 切换：setTheme('deep-blue')
 * ```
 */

/** 主题 key（与 main.css 的 [data-theme] 选择器一一对应） */
export type Theme = 'night' | 'day' | 'deep-blue' | 'parchment' | 'rose'

const THEME_STORAGE_KEY = 'ellia.question.theme'

/** 主题列表（UI 渲染循环使用） */
export const THEMES: { key: Theme; label: string }[] = [
  { key: 'night', label: '暗夜' },
  { key: 'day', label: '日间' },
  { key: 'deep-blue', label: '深蓝' },
  { key: 'parchment', label: '羊皮纸' },
  { key: 'rose', label: '雍容华丽' },
]

/** 启动时读取持久化主题，非法值回退默认 'night' */
export function resolveInitialTheme(): Theme {
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
  if (stored && THEMES.some((theme) => theme.key === stored)) {
    return stored as Theme
  }
  return 'night'
}

/** 应用初始主题（main.ts 挂载前调用，避免主题闪烁） */
export function applyInitialTheme(): void {
  document.documentElement.dataset.theme = resolveInitialTheme()
}

/** 切换主题并持久化 */
export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  window.localStorage.setItem(THEME_STORAGE_KEY, theme)
}

/** 读取当前主题（组件初始化用） */
export function currentTheme(): Theme {
  return (document.documentElement.dataset.theme as Theme | undefined) ?? 'night'
}
