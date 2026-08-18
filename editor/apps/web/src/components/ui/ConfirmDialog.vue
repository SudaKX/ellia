<script setup lang="ts">
import ModalDialog from './ModalDialog.vue'

withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    confirmLabel?: string
    cancelLabel?: string
    danger?: boolean
    busy?: boolean
  }>(),
  {
    confirmLabel: '确认',
    cancelLabel: '取消',
    danger: false,
    busy: false,
  },
)

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()
</script>

<template>
  <ModalDialog
    :open="open"
    :title="title"
    :confirm-label="confirmLabel"
    :cancel-label="cancelLabel"
    :danger="danger"
    :busy="busy"
    @confirm="emit('confirm')"
    @cancel="emit('cancel')"
  >
    <p>{{ message }}</p>
  </ModalDialog>
</template>