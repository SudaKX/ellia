/**
 * # useTheme — 主题管理
 *
 * 通过 `<html data-theme="xxx">` 切换 CSS 变量，所有组件无需改动。
 * 参照 i18n locale 切换模式：localStorage 持久化 + 启动时恢复。
 *
 * ## 支持的四种主题
 *
 * | key | 名称 | 基调 |
 * |---|---|---|
 * | `night` | 暗夜 | 暗色 + 警示红（当前默认） |
 * | `day` | 日间 | 浅色 + 黑白 |
 * | `deep-blue` | 深蓝 | 深蓝 + 亮蓝 |
 * | `parchment` | 羊皮纸 | 暖黄 + 棕褐 |
 *
 * ## 架构
 *
 * ```
 * main.ts → resolveInitialTheme() → <html data-theme="xxx">
 * Settings.vue → setTheme(name) → document.dataset + localStorage
 * main.css → [data-theme="xxx"] { ... } → CSS 变量自动切换
 * ```
 *
 * ## 与 i18n 的关键区别
 *
 * - 主题切换**不需要** page reload — CSS 变量实时响应
 * - 主题状态直接操作 `document.documentElement.dataset`
 * - 不经过 Pinia store（与 useTerminalCwd 模式一致）
 */

export type Theme = 'night' | 'day' | 'deep-blue' | 'parchment' | 'rose'

const THEME_STORAGE_KEY = 'ellia.desktop.theme'

/** 全部可用主题及其 i18n key */
export const THEMES: { key: Theme; i18nKey: string }[] = [
  { key: 'night', i18nKey: 'settings.themeOptions.night' },
  { key: 'day', i18nKey: 'settings.themeOptions.day' },
  { key: 'deep-blue', i18nKey: 'settings.themeOptions.deepBlue' },
  { key: 'parchment', i18nKey: 'settings.themeOptions.parchment' },
  { key: 'rose', i18nKey: 'settings.themeOptions.rose' },
]

function isSupportedTheme(value: string | null): value is Theme {
  return value != null && THEMES.some((t) => t.key === value)
}

/**
 * 启动时解析初始主题。
 * 优先级：localStorage → fallback 'night'
 */
export function resolveInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'night'

  const saved = window.localStorage.getItem(THEME_STORAGE_KEY)
  if (isSupportedTheme(saved)) return saved

  return 'night'
}

/**
 * 切换主题。
 * 写入 <html data-theme> 属性触发 CSS 变量切换 + localStorage 持久化。
 */
export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  window.localStorage.setItem(THEME_STORAGE_KEY, theme)
}
