import { createI18n } from 'vue-i18n'
import { watch } from 'vue'

import { enUS } from './locales/en-US'
import { zhCN } from './locales/zh-CN'
import { deDE } from './locales/de-DE'
import { jaJP } from './locales/ja-JP'
import { zhTW } from './locales/zh-TW'
import { binary } from './locales/binary'

const LOCALE_STORAGE_KEY = 'ellia.desktop.locale'

export const messages = {
  'en-US': enUS,
  'zh-CN': zhCN,
  'de-DE': deDE,
  'ja-JP': jaJP,
  'zh-TW': zhTW,
  binary,
}

export type SupportedLocale = keyof typeof messages

function isSupportedLocale(locale: string | null): locale is SupportedLocale {
  return locale != null && locale in messages
}

function resolveInitialLocale(): SupportedLocale {
  if (typeof window === 'undefined') return 'en-US'

  const savedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY)
  if (isSupportedLocale(savedLocale)) return savedLocale

  const navLang = window.navigator.language.toLowerCase()
  if (navLang.startsWith('zh')) {
    if (navLang.includes('tw') || navLang.includes('hk') || navLang === 'zh-hant') return 'zh-TW'
    return 'zh-CN'
  }
  if (navLang.startsWith('de')) return 'de-DE'
  if (navLang.startsWith('ja')) return 'ja-JP'
  return 'en-US'
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
