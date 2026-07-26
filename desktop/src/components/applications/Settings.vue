<script setup lang="ts">
/**
 * # Settings.vue — 桌面设置面板
 *
 * 当前仅包含语言切换功能。
 * 使用自定义下拉组件替代原生 <select>，避免下拉菜单超出窗口边界。
 */

import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown } from 'lucide-vue-next'

import { setLocale, type SupportedLocale } from '@/i18n'

const { locale, t } = useI18n({ useScope: 'global' })

const languageOptions: { value: SupportedLocale; labelKey: string }[] = [
  { value: 'en-US', labelKey: 'settings.languageOptions.enUS' },
  { value: 'zh-CN', labelKey: 'settings.languageOptions.zhCN' },
  { value: 'zh-TW', labelKey: 'settings.languageOptions.zhTW' },
  { value: 'de-DE', labelKey: 'settings.languageOptions.deDE' },
  { value: 'ja-JP', labelKey: 'settings.languageOptions.jaJP' },
]

const isOpen = ref(false)

function select(option: { value: SupportedLocale }) {
  setLocale(option.value)
  isOpen.value = false
}

/** 点击遮罩层关闭 */
function closeDropdown(e: MouseEvent) {
  if (e.target === e.currentTarget) {
    isOpen.value = false
  }
}
</script>

<template>
  <section class="settings" :aria-label="t('applications.settings.title')">
    <header class="settings__header">
      <p class="settings__eyebrow">{{ t('settings.label') }}</p>
      <h2 class="settings__title">{{ t('applications.settings.title') }}</h2>
    </header>

    <div class="settings__field">
      <span class="settings__field-label">{{ t('settings.language') }}</span>
      <span class="settings__field-description">{{ t('settings.languageDescription') }}</span>

      <!-- 自定义下拉 -->
      <div class="dropdown" :class="{ 'dropdown--open': isOpen }">
        <button class="dropdown__trigger" @click="isOpen = !isOpen">
          <span>{{ t(languageOptions.find(o => o.value === locale)?.labelKey ?? '') }}</span>
          <ChevronDown :size="14" :stroke-width="1.8" class="dropdown__chevron" />
        </button>

        <div v-if="isOpen" class="dropdown__menu">
          <button
            v-for="option in languageOptions"
            :key="option.value"
            class="dropdown__item"
            :class="{ 'dropdown__item--active': option.value === locale }"
            @click="select(option)"
          >
            {{ t(option.labelKey) }}
          </button>
        </div>
      </div>
    </div>

    <!-- 点击菜单外关闭 -->
    <div v-if="isOpen" class="dropdown__backdrop" @click="closeDropdown" />
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
  border: 1px solid var(--line-default);
  border-top: none;
  background: var(--surface-panel);
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

/* 透明遮罩：点击菜单外关闭 */
.dropdown__backdrop {
  position: fixed;
  inset: 0;
  z-index: 5;
}
</style>
