<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

export interface MultiSelectOption {
  label: string
  value: string
}

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    options: MultiSelectOption[]
    placeholder?: string
    searchPlaceholder?: string
    disabled?: boolean
  }>(),
  {
    placeholder: '选择...',
    searchPlaceholder: '搜索...',
    disabled: false,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
}>()

const container = ref<HTMLElement | null>(null)
const searchInputRef = ref<HTMLInputElement | null>(null)
const open = ref(false)
const query = ref('')

const labelByValue = computed(() => new Map(props.options.map((option) => [option.value, option.label])))
const selectedSet = computed(() => new Set(props.modelValue))

const filteredOptions = computed(() => {
  const q = query.value.trim().toLowerCase()
  return props.options.filter((option) => {
    if (selectedSet.value.has(option.value)) return false
    if (!q) return true
    return (
      option.label.toLowerCase().includes(q) ||
      option.value.toLowerCase().includes(q)
    )
  })
})

function toggle(): void {
  if (props.disabled) return
  open.value = !open.value
}

function select(option: MultiSelectOption): void {
  if (selectedSet.value.has(option.value)) return
  emit('update:modelValue', [...props.modelValue, option.value])
  open.value = false
  query.value = ''
}

function remove(value: string): void {
  emit('update:modelValue', props.modelValue.filter((item) => item !== value))
}

function labelOf(value: string): string {
  return labelByValue.value.get(value) ?? value
}

function onClickOutside(event: PointerEvent): void {
  if (container.value && !container.value.contains(event.target as Node)) {
    open.value = false
  }
}

watch(open, async (value) => {
  if (value) {
    query.value = ''
    await nextTick()
    searchInputRef.value?.focus()
  }
})

onMounted(() => {
  document.addEventListener('pointerdown', onClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onClickOutside)
})
</script>

<template>
  <div ref="container" class="multi-select">
    <div v-if="modelValue.length > 0" class="multi-select__chips">
      <span v-for="value in modelValue" :key="value" class="multi-select__chip">
        <span class="multi-select__chip-label">{{ labelOf(value) }}</span>
        <button
          class="multi-select__chip-remove"
          type="button"
          :disabled="disabled"
          title="移除"
          @click="remove(value)"
        >
          ×
        </button>
      </span>
    </div>

    <button
      class="multi-select__trigger"
      type="button"
      :disabled="disabled"
      :aria-expanded="open"
      @click="toggle"
    >
      <span class="multi-select__trigger-label">
        {{ modelValue.length > 0 ? `已选 ${modelValue.length} 项` : placeholder }}
      </span>
      <span class="multi-select__caret" aria-hidden="true">▾</span>
    </button>

    <div v-if="open" class="multi-select__menu">
      <input
        ref="searchInputRef"
        v-model="query"
        class="multi-select__search"
        type="text"
        :placeholder="searchPlaceholder"
      />
      <div class="multi-select__options">
        <div v-if="filteredOptions.length === 0" class="multi-select__empty">无可选项</div>
        <button
          v-for="option in filteredOptions"
          :key="option.value"
          class="multi-select__option"
          type="button"
          @click="select(option)"
        >
          {{ option.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.multi-select {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.85rem;
}

.multi-select__trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  width: 100%;
  min-height: 32px;
  padding: 0.25rem 0.6rem;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  color: var(--md-sys-color-on-surface, #1d1b20);
  cursor: pointer;
  text-align: left;
}

.multi-select__trigger:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.multi-select__trigger-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.multi-select__caret {
  font-size: 1rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.multi-select__menu {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 220px;
  padding: 4px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.15);
}

.multi-select__search {
  width: 100%;
  min-height: 28px;
  padding: 4px 8px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
  font-size: 0.8rem;
}

.multi-select__search:focus-visible {
  outline: 2px solid var(--md-sys-color-primary, #6750a4);
  outline-offset: 1px;
}

.multi-select__options {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.multi-select__empty {
  padding: 14px 10px;
  text-align: center;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font-size: 0.8rem;
}

.multi-select__option {
  display: block;
  width: 100%;
  padding: 6px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--md-sys-color-on-surface, #1d1b20);
  text-align: left;
  cursor: pointer;
  font-size: 0.85rem;
}

.multi-select__option:hover {
  background: var(--md-sys-color-surface-container-highest, #e6e0e9);
}

.multi-select__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.multi-select__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  padding: 2px 4px 2px 8px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 999px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font-size: 0.78rem;
}

.multi-select__chip-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.multi-select__chip-remove {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  min-width: 18px;
  min-height: 18px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
}

.multi-select__chip-remove:hover {
  background: var(--md-sys-color-error-container, #f9dedc);
  color: var(--md-sys-color-on-error-container, #410e0b);
}
</style>
