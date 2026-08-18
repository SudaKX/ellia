<script setup lang="ts">
import { computed } from 'vue'

import type { EntityRecord } from '@ellia/puzzle-schema'

import CodeEditor from './CodeEditor.vue'

const props = defineProps<{
  entity: EntityRecord
}>()

const script = computed(() => props.entity.state as Extract<EntityRecord['state'], { body: { lines: string[] } }>)
const dataPath = computed(() => `${props.entity.id}@state:/body`)
const modelValue = computed(() => script.value.body.lines.join('\n'))

function makePatchValue(value: string): unknown {
  return {
    ...script.value.body,
    lines: value.split('\n'),
  }
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