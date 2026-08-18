<script setup lang="ts">
import DropdownSelect from '../ui/DropdownSelect.vue'

defineProps<{
  kinds: string[]
  groups: string[]
}>()

const filter = defineModel<{ kind: string; group: string }>({ required: true })

function optionList(values: string[]): Array<{ label: string; value: string }> {
  return values.map((value) => ({ label: value, value }))
}

function onKindChange(value: string | number): void {
  filter.value = { ...filter.value, kind: String(value) }
}

function onGroupChange(value: string | number): void {
  filter.value = { ...filter.value, group: String(value) }
}
</script>

<template>
  <div class="entity-filter-bar">
    <label class="entity-filter">
      <span>kind</span>
      <DropdownSelect
        :options="[{ label: '全部', value: '' }, ...optionList(kinds)]"
        :model-value="filter.kind"
        placeholder="全部"
        @update:model-value="onKindChange"
      />
    </label>
    <label class="entity-filter">
      <span>group</span>
      <DropdownSelect
        :options="[{ label: '全部', value: '' }, ...optionList(groups)]"
        :model-value="filter.group"
        placeholder="全部"
        @update:model-value="onGroupChange"
      />
    </label>
  </div>
</template>

<style scoped>
.entity-filter-bar {
  display: flex;
  gap: 10px;
  padding: 8px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
}

.entity-filter {
  display: grid;
  gap: 4px;
  font-size: 0.75rem;
}

.entity-filter :deep(.dropdown) {
  min-width: 130px;
}
</style>