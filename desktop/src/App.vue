<script setup lang="ts">
import { provide } from 'vue'
import { RouterView } from 'vue-router'

import FilterHost from '@/components/desktop/FilterHost.vue'
import { createFilterService, FilterServiceKey } from '@/composables/useFilterService'

const filterService = createFilterService()
const filterInstances = filterService.instances

provide(FilterServiceKey, filterService)
</script>

<template>
  <FilterHost :instances="filterInstances" @ready="filterService.markReady" />
  <RouterView />
</template>
