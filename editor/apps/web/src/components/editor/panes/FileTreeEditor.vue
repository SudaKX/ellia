<script setup lang="ts">
import type { EntityRecord } from '@ellia/puzzle-schema'

import FormEditor from './FormEditor.vue'

defineProps<{
  entity: EntityRecord
}>()
</script>

<template>
  <FormEditor :entity="entity" />
</template>