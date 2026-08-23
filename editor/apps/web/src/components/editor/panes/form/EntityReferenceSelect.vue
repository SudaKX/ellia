<script setup lang="ts">
import { computed } from 'vue'

import { useEntitiesStore } from '../../../../stores/entities'
import DropdownSelect from '../../../ui/DropdownSelect.vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    namespace: string
    disabled?: boolean
    valueAsId?: boolean
    placeholder?: string
    searchable?: boolean
  }>(),
  {
    disabled: false,
    valueAsId: false,
    placeholder: '选择引用',
    searchable: false,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const entitiesStore = useEntitiesStore()

const options = computed(() =>
  entitiesStore.entityList
    .filter((entity) => entity.resource_id.startsWith(`${props.namespace}:`))
    .map((entity) => ({
      label: entity.resource_id,
      value: props.valueAsId ? entity.id : entity.resource_id,
    })),
)
</script>

<template>
  <DropdownSelect
    :options="options"
    :model-value="modelValue"
    :disabled="disabled"
    :placeholder="placeholder"
    :searchable="searchable"
    @update:model-value="(value) => emit('update:modelValue', String(value))"
  />
</template>
