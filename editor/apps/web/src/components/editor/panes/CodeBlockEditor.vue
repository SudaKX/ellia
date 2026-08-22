<script setup lang="ts">
import { computed } from 'vue'

import type { EntityRecord } from '@ellia/puzzle-schema'

import CodeEditor from './CodeEditor.vue'

const props = defineProps<{
  entity: EntityRecord
}>()

const code = computed(
  () => props.entity.state as Extract<EntityRecord['state'], { content: string }>,
)
const dataPath = computed(() => `${props.entity.id}@state:/content`)
const modelValue = computed(() => code.value.content)

function makePatchValue(value: string): unknown {
  return value
}
</script>

<template>
  <CodeEditor
    :entity="entity"
    :data-path="dataPath"
    :model-value="modelValue"
    :patch-value="makePatchValue"
  />
</template>
