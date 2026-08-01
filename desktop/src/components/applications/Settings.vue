<script setup lang="ts">
/**
 * # Settings.vue — 桌面设置面板
 *
 * 包含语言切换和主题切换。
 * 使用自定义下拉组件替代原生 <select>，避免下拉菜单超出窗口边界。
 */

import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown } from 'lucide-vue-next'

import { setLocale, type SupportedLocale } from '@/i18n'
import { setTheme, THEMES, type Theme } from '@/composables/useTheme'

const { locale, t } = useI18n({ useScope: 'global' })

const languageOptions: { value: SupportedLocale; labelKey: string }[] = [
  { value: 'en-US', labelKey: 'settings.languageOptions.enUS' },
  { value: 'zh-CN', labelKey: 'settings.languageOptions.zhCN' },
  { value: 'zh-TW', labelKey: 'settings.languageOptions.zhTW' },
  { value: 'de-DE', labelKey: 'settings.languageOptions.deDE' },
  { value: 'ja-JP', labelKey: 'settings.languageOptions.jaJP' },
  { value: 'binary', labelKey: 'settings.languageOptions.binary' },
]

/** 当前主题，与 <html data-theme> 同步 */
const currentTheme = ref<Theme>(
  (document.documentElement.dataset.theme as Theme) || 'night',
)

/**
 * 当前展开的下拉菜单：'language' | 'theme'，null 表示全部收起。
 * 使用单开模式（与顶部状态栏的 activeMenuId 一致）：同一时间只允许一个下拉展开，
 * 打开一个会自动收起另一个，避免两个下拉菜单互相覆盖。
 */
const openMenu = ref<'language' | 'theme' | null>(null)

function toggleMenu(menu: 'language' | 'theme') {
  openMenu.value = openMenu.value === menu ? null : menu
}

function selectLang(option: { value: SupportedLocale }) {
  openMenu.value = null
  setLocale(option.value)
}

function selectTheme(theme: Theme) {
  openMenu.value = null
  currentTheme.value = theme
  setTheme(theme)
}

/** 点击设置面板非下拉区域时收起所有下拉，不阻塞滚轮等事件 */
function handleSettingsClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.dropdown')) {
    openMenu.value = null
  }
}
</script>

<template>
  <section class="settings" :aria-label="t('applications.settings.title')" @click="handleSettingsClick">
    <header class="settings__header">
      <p class="settings__eyebrow">{{ t('settings.label') }}</p>
      <h2 class="settings__title">{{ t('applications.settings.title') }}</h2>
    </header>

    <!-- 语言 -->
    <div class="settings__field">
      <span class="settings__field-label">{{ t('settings.language') }}</span>
      <span class="settings__field-description">{{ t('settings.languageDescription') }}</span>
      <div class="dropdown" :class="{ 'dropdown--open': openMenu === 'language' }">
        <button class="dropdown__trigger" @click="toggleMenu('language')">
          <span>{{ t(languageOptions.find(o => o.value === locale)?.labelKey ?? '') }}</span>
          <ChevronDown :size="14" :stroke-width="1.8" class="dropdown__chevron" />
        </button>
        <div v-if="openMenu === 'language'" class="dropdown__menu">
          <button
            v-for="option in languageOptions"
            :key="option.value"
            class="dropdown__item"
            :class="{ 'dropdown__item--active': option.value === locale }"
            @click="selectLang(option)"
          >
            {{ t(option.labelKey) }}
          </button>
        </div>
      </div>
    </div>

    <!-- 主题 -->
    <div class="settings__field">
      <span class="settings__field-label">{{ t('settings.theme') }}</span>
      <span class="settings__field-description">{{ t('settings.themeDescription') }}</span>
      <div class="dropdown" :class="{ 'dropdown--open': openMenu === 'theme' }">
        <button class="dropdown__trigger" @click="toggleMenu('theme')">
          <span>{{ t(THEMES.find(t => t.key === currentTheme)?.i18nKey ?? '') }}</span>
          <ChevronDown :size="14" :stroke-width="1.8" class="dropdown__chevron" />
        </button>
        <div v-if="openMenu === 'theme'" class="dropdown__menu">
          <button
            v-for="theme in THEMES"
            :key="theme.key"
            class="dropdown__item"
            :class="{ 'dropdown__item--active': theme.key === currentTheme }"
            @click="selectTheme(theme.key)"
          >
            {{ t(theme.i18nKey) }}
          </button>
        </div>
      </div>
    </div>

  </section>
</template>

<style scoped>
.settings {
  display: grid;
  min-height: 100%;
  align-content: start;
  gap: 24px;
  padding: 20px;
}

.settings__header {
  display: grid;
  gap: 6px;
}

.settings__eyebrow {
  margin: 0;
  color: var(--signal-red-soft);
  font: 700 10px var(--font-mono);
  text-transform: uppercase;
}

.settings__title {
  margin: 0;
  color: var(--text-primary);
  font: 600 18px var(--font-ui);
}

.settings__field {
  display: grid;
  gap: 7px;
  max-width: 320px;
}

.settings__field-label {
  color: var(--text-primary);
  font: 600 12px var(--font-ui);
}

.settings__field-description {
  color: var(--text-muted);
  font: 12px/1.45 var(--font-ui);
}

/* ── 自定义下拉 ── */
.dropdown {
  position: relative;
}

.dropdown__trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: var(--surface-panel);
  font: 12px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s;
}

.dropdown__trigger:hover {
  border-color: var(--text-muted);
}

.dropdown--open .dropdown__trigger {
  border-color: var(--signal-red-soft);
}

.dropdown__chevron {
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform 0.12s;
}

.dropdown--open .dropdown__chevron {
  transform: rotate(180deg);
}

.dropdown__menu {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 10;
  max-height: 180px;
  overflow-y: auto;
  border: 1px solid var(--line-default);
  border-top: none;
  background: var(--surface-panel);
}

/* FakeOS 风格滚动条 */
.dropdown__menu::-webkit-scrollbar {
  width: 6px;
}
.dropdown__menu::-webkit-scrollbar-track {
  background: var(--surface-panel);
}
.dropdown__menu::-webkit-scrollbar-thumb {
  background: var(--line-default);
}
.dropdown__menu::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.dropdown__item {
  display: block;
  width: 100%;
  padding: 7px 10px;
  border: none;
  border-radius: 0;
  color: var(--text-secondary);
  background: transparent;
  font: 12px var(--font-ui);
  text-align: left;
  cursor: pointer;
  transition: background-color 0.12s, color 0.12s;
}

.dropdown__item:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.dropdown__item--active {
  color: var(--signal-mint);
  background: var(--surface-panel);
}
</style>
