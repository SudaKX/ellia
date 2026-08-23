<script setup lang="ts">
import type { ChoiceQuestionData } from '@ellia/puzzle-schema'

const data = defineModel<ChoiceQuestionData>({ required: true })

function updateSingle(event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  data.value = { ...data.value, single: checked }
}

function updateOption(index: number, value: string): void {
  const options = [...data.value.options]
  options[index] = value
  data.value = { ...data.value, options }
}

function addOption(): void {
  data.value = { ...data.value, options: [...data.value.options, ''] }
}

function removeOption(index: number): void {
  data.value = {
    ...data.value,
    options: data.value.options.filter((_, optionIndex) => optionIndex !== index),
  }
}
</script>

<template>
  <div class="choice-editor">
    <label class="choice-editor__single">
      <input type="checkbox" :checked="data.single" @change="updateSingle" />
      <span>单项选择</span>
    </label>

    <div class="choice-editor__options">
      <div v-for="(option, index) in data.options" :key="index" class="choice-editor__option-row">
        <input
          class="choice-editor__option-input"
          type="text"
          :value="option"
          placeholder="选项内容"
          @input="updateOption(index, ($event.target as HTMLInputElement).value)"
        />
        <button
          class="btn btn--small btn--text"
          type="button"
          :disabled="data.options.length <= 1"
          @click="removeOption(index)"
        >
          删除
        </button>
      </div>
      <button class="btn btn--small btn--tonal" type="button" @click="addOption">
        ＋ 添加选项
      </button>
    </div>
  </div>
</template>

<style scoped>
.choice-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
}

.choice-editor__single {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.choice-editor__single input {
  accent-color: var(--md-sys-color-primary, #6750a4);
  margin: 0;
}

.choice-editor__options {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.choice-editor__option-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.choice-editor__option-input {
  flex: 1;
  min-height: 30px;
  padding: 0.25rem 0.6rem;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
  font-size: 0.85rem;
}
</style>
