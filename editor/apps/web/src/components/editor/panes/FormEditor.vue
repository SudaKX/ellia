<script setup lang="ts">
import { computed } from 'vue'

import type { EntityRecord } from '@ellia/puzzle-schema'

import { FORM_SPECS } from './form/formSpecs'
import FallbackEditor from './FallbackEditor.vue'
import FormField from './form/FormField.vue'

const props = defineProps<{
  entity: EntityRecord
}>()

const spec = computed(() => FORM_SPECS[props.entity.kind] ?? null)
const specEntries = computed(() => Object.entries(spec.value ?? {}))
const stateRecord = computed(() => props.entity.state as unknown as Record<string, unknown>)

function fieldDataPath(key: string): string {
  return `${props.entity.id}@state:/${key}`
}

function shouldRenderField(key: string): boolean {
  const fieldSpec = spec.value?.[key]
  if (!fieldSpec) return false
  if (fieldSpec.hidden) return false
  // optional 字段未设置时也渲染，显示“未设置”并提供设置入口
  return true
}
</script>

<template>
  <div class="form-editor">
    <template v-if="spec">
      <div class="form-editor__structured">
        <template v-for="[key, fieldSpec] in specEntries" :key="key">
          <FormField
            v-if="shouldRenderField(key)"
            :entity="entity"
            :field-name="key"
            :field-spec="fieldSpec"
            :data-path="fieldDataPath(key)"
            :model-value="stateRecord[key]"
          />
        </template>
      </div>
    </template>

    <FallbackEditor v-else :entity="entity" embedded />
  </div>
</template>

<style scoped>
.form-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  padding: 12px;
  box-sizing: border-box;
  overflow-y: auto;
}

.form-editor__structured {
  display: grid;
  gap: 10px;
  align-content: start;
}
</style>
