<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { useFilesStore } from '../../../../stores/files'
import DropdownSelect from '../../../ui/DropdownSelect.vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    disabled?: boolean
    placeholder?: string
  }>(),
  {
    disabled: false,
    placeholder: '请选择文件',
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const filesStore = useFilesStore()

const options = computed(() =>
  filesStore.files.map((file) => ({
    label: file.original_name ?? file.file_id,
    value: file.file_id,
  })),
)

onMounted(() => {
  if (filesStore.files.length === 0) {
    void filesStore.refresh()
  }
})
</script>

<template>
  <DropdownSelect
    searchable
    :options="options"
    :model-value="modelValue"
    :disabled="disabled"
    :placeholder="placeholder"
    @update:model-value="(value) => emit('update:modelValue', String(value))"
  />
</template>
