<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { setLocale, type SupportedLocale } from '@/i18n'

const { locale, t } = useI18n({ useScope: 'global' })

const languageOptions: { value: SupportedLocale; labelKey: string }[] = [
  { value: 'en-US', labelKey: 'settings.languageOptions.enUS' },
  { value: 'zh-CN', labelKey: 'settings.languageOptions.zhCN' },
]

function handleLocaleChange(event: Event) {
  setLocale((event.target as HTMLSelectElement).value as SupportedLocale)
}
</script>

<template>
  <section class="settings" :aria-label="t('applications.settings.title')">
    <header class="settings__header">
      <p class="settings__eyebrow">{{ t('settings.label') }}</p>
      <h2 class="settings__title">{{ t('applications.settings.title') }}</h2>
    </header>

    <label class="settings__field">
      <span class="settings__field-label">{{ t('settings.language') }}</span>
      <span class="settings__field-description">{{ t('settings.languageDescription') }}</span>
      <select :value="locale" @change="handleLocaleChange">
        <option v-for="option in languageOptions" :key="option.value" :value="option.value">
          {{ t(option.labelKey) }}
        </option>
      </select>
    </label>
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

.settings select {
  width: 100%;
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: var(--surface-panel);
  font: 12px var(--font-ui);
}

.settings select:focus-visible {
  outline: 2px solid var(--signal-red-soft);
  outline-offset: 2px;
}
</style>
