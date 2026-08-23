<script setup lang="ts">
import type { ChoiceQuestionData } from '@ellia/puzzle-schema'

defineProps<{
  data: ChoiceQuestionData
}>()
</script>

<template>
  <div class="choice-preview">
    <div v-if="data.single" class="choice-preview__options">
      <label v-for="(option, index) in data.options" :key="index" class="choice-preview__option">
        <input type="radio" disabled />
        <span>{{ option }}</span>
      </label>
    </div>
    <div v-else class="choice-preview__options">
      <label v-for="(option, index) in data.options" :key="index" class="choice-preview__option">
        <input type="checkbox" disabled />
        <span>{{ option }}</span>
      </label>
    </div>
  </div>
</template>

<style scoped>
.choice-preview {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 0 0;
}

.choice-preview__options {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.choice-preview__option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font-size: 0.85rem;
}

.choice-preview__option input {
  accent-color: var(--md-sys-color-primary, #6750a4);
  margin: 0;
}
</style>
