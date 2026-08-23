<script setup lang="ts">
import type { TextQuestionData } from '@ellia/puzzle-schema'

defineProps<{
  data: TextQuestionData
}>()
</script>

<template>
  <div class="text-preview">
    <input class="text-preview__input" type="text" disabled placeholder="填空题答案" />
    <p v-if="data.format" class="text-preview__hint">格式：{{ data.format }}</p>
    <p v-else class="text-preview__hint">不校验格式</p>
  </div>
</template>

<style scoped>
.text-preview {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 0 0;
}

.text-preview__input {
  width: 100%;
  min-height: 32px;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font: inherit;
  font-size: 0.85rem;
  box-sizing: border-box;
}

.text-preview__hint {
  margin: 0;
  font-size: 0.75rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  overflow-wrap: anywhere;
}
</style>
