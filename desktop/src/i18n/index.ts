import { createI18n } from 'vue-i18n'
import { watch } from 'vue'

import { enUS } from './locales/en-US'
import { zhCN } from './locales/zh-CN'

const LOCALE_STORAGE_KEY = 'ellia.desktop.locale'

export const messages = {
  'en-US': enUS,
  'zh-CN': zhCN,
}

export type SupportedLocale = keyof typeof messages

function isSupportedLocale(locale: string | null): locale is SupportedLocale {
  return locale === 'en-US' || locale === 'zh-CN'
}

function resolveInitialLocale(): SupportedLocale {
  if (typeof window === 'undefined') return 'en-US'

  const savedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY)
  if (isSupportedLocale(savedLocale)) return savedLocale

  return window.navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US'
}

export const i18n = createI18n({
  legacy: false,
  locale: resolveInitialLocale(),
  fallbackLocale: 'en-US',
  globalInjection: false,
  messages,
})

watch(
  i18n.global.locale,
  (locale) => {
    document.documentElement.lang = locale
  },
  { immediate: true },
)

export function setLocale(locale: SupportedLocale) {
  i18n.global.locale.value = locale
  window.localStorage.setItem(LOCALE_STORAGE_KEY, locale)
}
