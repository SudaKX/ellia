<script setup lang="ts">
import type { TextQuestionData } from '@ellia/puzzle-schema'

const data = defineModel<TextQuestionData>({ required: true })

function updateFormat(event: Event): void {
  const value = (event.target as HTMLInputElement).value
  data.value = { ...data.value, format: value.trim() === '' ? null : value }
}
</script>

<template>
  <div class="text-editor">
    <label class="text-editor__field">
      <span class="text-editor__label">输入校验正则（可选）</span>
      <input
        class="text-editor__input"
        type="text"
        :value="data.format ?? ''"
        placeholder="例如 ^[0-9]{4}$，留空表示不校验"
        spellcheck="false"
        @input="updateFormat"
      />
    </label>
    <p class="text-editor__hint">空字符串或 null 表示不校验格式。</p>
  </div>
</template>

<style scoped>
.text-editor {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
}

.text-editor__field {
  display: grid;
  gap: 4px;
}

.text-editor__label {
  font-size: 0.8rem;
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.text-editor__input {
  width: 100%;
  min-height: 32px;
  padding: 0.25rem 0.6rem;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
  font-size: 0.85rem;
  box-sizing: border-box;
}

.text-editor__hint {
  margin: 0;
  font-size: 0.75rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}
</style>
