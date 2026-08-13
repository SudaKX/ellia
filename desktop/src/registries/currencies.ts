/**
 * # 代币展示货币注册表
 *
 * 同一份代币余额按界面语言映射到不同的"货币符号"，这是纯展示层本地化：
 * 后端余额本身不区分币种，符号仅用于 FakeOS 界面叙事。
 *
 * | 语言    | 符号 | 货币                     |
 * | ------- | ---- | ------------------------ |
 * | zh-CN   | ¥    | 人民币                   |
 * | zh-TW   | NT$  | 新台币（可换港币 HK$ / 澳门币 MOP$） |
 * | ja-JP   | ¥    | 日元                     |
 * | en-US   | $    | 美元                     |
 * | de-DE   | €    | 欧元（马克已退出流通）   |
 * | binary  | ₿    | 比特币                   |
 */

import type { SupportedLocale } from '@/i18n'

export interface CurrencyDisplay {
  /** 展示符号，如 ¥ / NT$ / € / ₿ */
  symbol: string
  /** ISO 4217 货币代码；比特币无标准代码时为 null */
  currencyCode: string | null
}

export const CURRENCIES: Record<SupportedLocale, CurrencyDisplay> = {
  'zh-CN': { symbol: '¥', currencyCode: 'CNY' },
  'zh-TW': { symbol: 'NT$', currencyCode: 'TWD' },
  'ja-JP': { symbol: '¥', currencyCode: 'JPY' },
  'en-US': { symbol: '$', currencyCode: 'USD' },
  'de-DE': { symbol: '€', currencyCode: 'EUR' },
  binary: { symbol: '₿', currencyCode: null },
}

/** 数字分组使用的 Intl locale（binary 沿用 en-US 的分组规则） */
const NUMBER_LOCALES: Record<SupportedLocale, string> = {
  'zh-CN': 'zh-CN',
  'zh-TW': 'zh-TW',
  'ja-JP': 'ja-JP',
  'en-US': 'en-US',
  'de-DE': 'de-DE',
  binary: 'en-US',
}

export function getCurrency(locale: SupportedLocale | string): CurrencyDisplay {
  return CURRENCIES[locale as SupportedLocale] ?? CURRENCIES['en-US']
}

/** 千分位数字，如 1,234 / 128 */
export function formatTokenNumber(amount: number, locale: SupportedLocale | string): string {
  const numberLocale = NUMBER_LOCALES[locale as SupportedLocale] ?? 'en-US'
  return new Intl.NumberFormat(numberLocale, { maximumFractionDigits: 0 }).format(amount)
}

/** 将代币余额格式化为"符号 + 千分位数字"，如 ¥1,234 / ₿128 */
export function formatTokenAmount(amount: number, locale: SupportedLocale | string): string {
  return `${getCurrency(locale).symbol}${formatTokenNumber(amount, locale)}`
}
