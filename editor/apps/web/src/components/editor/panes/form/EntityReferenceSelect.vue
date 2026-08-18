<script setup lang="ts">
import { computed } from 'vue'

import { useEntitiesStore } from '../../../../stores/entities'
import DropdownSelect from '../../../ui/DropdownSelect.vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    namespace: string
    valueMode?: 'entity_id' | 'id_part'
    disabled?: boolean
  }>(),
  {
    valueMode: 'entity_id',
    disabled: false,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const entitiesStore = useEntitiesStore()

const options = computed(() =>
  entitiesStore.entityList
    .filter((entity) => entity.resource_id.startsWith(`${props.namespace}:`))
    .map((entity) => {
      const idPart = entity.resource_id.slice(props.namespace.length + 1)
      return {
        label: idPart,
        value: props.valueMode === 'entity_id' ? entity.id : idPart,
      }
    }),
)
</script>

<template>
  <DropdownSelect
    :options="options"
    :model-value="modelValue"
    :disabled="disabled"
    placeholder="选择引用"
    @update:model-value="(value) => emit('update:modelValue', String(value))"
  />
</template>