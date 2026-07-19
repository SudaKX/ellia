<script setup lang="ts">
import { filterRegistry } from '@/filters'
import type { FilterInstance } from '@/composables/useFilterService'

defineProps<{
  instances: FilterInstance[]
}>()
</script>

<template>
  <component
    v-for="instance in instances"
    :is="filterRegistry[instance.filterType].component"
    :key="instance.instanceId"
    :filter-id="instance.filterId"
    :options="instance.options"
  />
</template>
