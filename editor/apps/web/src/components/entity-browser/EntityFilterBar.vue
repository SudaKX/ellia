<script setup lang="ts">
import DropdownSelect from '../ui/DropdownSelect.vue'
import TextField from '../ui/TextField.vue'

defineProps<{
  kinds: string[]
  groups: string[]
}>()

const filter = defineModel<{ kind: string; group: string; search: string }>({
  required: true,
})

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
      <span>类型</span>
      <DropdownSelect
        :options="[{ label: '全部', value: '' }, ...optionList(kinds)]"
        :model-value="filter.kind"
        placeholder="全部"
        searchable
        search-placeholder="搜索类型..."
        @update:model-value="onKindChange"
      />
    </label>
    <label class="entity-filter">
      <span>分组</span>
      <DropdownSelect
        :options="[{ label: '全部', value: '' }, ...optionList(groups)]"
        :model-value="filter.group"
        placeholder="全部"
        searchable
        search-placeholder="搜索分组..."
        @update:model-value="onGroupChange"
      />
    </label>
    <label class="entity-filter entity-filter--search">
      <span>资源标识符</span>
      <TextField v-model="filter.search" placeholder="搜索资源标识符..." />
    </label>
  </div>
</template>

<style scoped>
.entity-filter-bar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  gap: 10px;
  padding: 8px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
}

.entity-filter {
  flex: 1 1 50%;
  max-width: 240px;
  min-width: 0;
  display: grid;
  gap: 4px;
  font-size: 0.75rem;
}

.entity-filter--search {
  flex: 1 1 100%;
  max-width: none;
}

.entity-filter :deep(.dropdown) {
  width: 100%;
  min-width: 0;
}
</style>
