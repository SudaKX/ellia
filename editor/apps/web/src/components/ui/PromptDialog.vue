<script setup lang="ts">
import { ref, watch } from 'vue'

import ModalDialog from './ModalDialog.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    message?: string
    initialValue: string
    readonly?: boolean
    confirmLabel?: string
    cancelLabel?: string
  }>(),
  {
    message: '',
    readonly: false,
    confirmLabel: '确认',
    cancelLabel: '取消',
  },
)

const emit = defineEmits<{
  (e: 'confirm', value: string): void
  (e: 'cancel'): void
}>()

const value = ref(props.initialValue)

watch(
  () => props.open,
  (open) => {
    if (open) value.value = props.initialValue
  },
)
</script>

<template>
  <ModalDialog
    :open="open"
    :title="title"
    :confirm-label="confirmLabel"
    :cancel-label="cancelLabel"
    :show-cancel="!readonly"
    @confirm="emit('confirm', value)"
    @cancel="emit('cancel')"
  >
    <p v-if="message">{{ message }}</p>
    <input
      v-model="value"
      class="prompt-input"
      :readonly="readonly"
      :disabled="readonly"
      @keyup.enter="emit('confirm', value)"
    />
  </ModalDialog>
</template>

<style scoped>
.prompt-input {
  width: 100%;
  min-height: 36px;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
}
</style>