<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

export interface DropdownOption {
  label: string
  value: string | number
}

const props = withDefaults(
  defineProps<{
    options: DropdownOption[]
    modelValue: string | number
    disabled?: boolean
    placeholder?: string
    /** 是否在菜单顶部显示搜索框；开启后按 label / value 过滤选项 */
    searchable?: boolean
    searchPlaceholder?: string
  }>(),
  {
    disabled: false,
    placeholder: '请选择',
    searchable: false,
    searchPlaceholder: '搜索...',
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number): void
}>()

const container = ref<HTMLElement | null>(null)
const searchInputRef = ref<HTMLInputElement | null>(null)
const open = ref(false)
const highlightIndex = ref(-1)
const query = ref('')

const selectedLabel = computed(
  () =>
    props.options.find((option) => String(option.value) === String(props.modelValue))?.label ??
    props.placeholder,
)

const filteredOptions = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!props.searchable || !q) return props.options
  return props.options.filter(
    (option) =>
      option.label.toLowerCase().includes(q) ||
      String(option.value).toLowerCase().includes(q),
  )
})

function toggle(): void {
  if (props.disabled) return
  open.value = !open.value
}

function select(option: DropdownOption): void {
  emit('update:modelValue', option.value)
  open.value = false
  query.value = ''
  highlightIndex.value = -1
}

function onSearchInput(): void {
  highlightIndex.value = -1
}

function onKeydown(event: KeyboardEvent): void {
  if (props.disabled) return

  const inSearch = event.target === searchInputRef.value

  if (event.key === 'Enter' || event.key === ' ') {
    if (inSearch) {
      if (event.key === 'Enter') {
        event.preventDefault()
        const option = filteredOptions.value[highlightIndex.value]
        if (open.value && option !== undefined) {
          select(option)
        } else {
          open.value = false
        }
      }
      // Space in search input keeps its default typing behavior.
      return
    }
    event.preventDefault()
    toggle()
    return
  }

  if (event.key === 'Escape') {
    open.value = false
    return
  }

  if (!open.value) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      open.value = true
      highlightIndex.value = 0
    }
    return
  }

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    highlightIndex.value = Math.min(filteredOptions.value.length - 1, highlightIndex.value + 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    highlightIndex.value = Math.max(0, highlightIndex.value - 1)
  } else if (event.key === 'Home') {
    highlightIndex.value = 0
  } else if (event.key === 'End') {
    highlightIndex.value = filteredOptions.value.length - 1
  } else if (event.key === 'Enter' && highlightIndex.value >= 0) {
    const option = filteredOptions.value[highlightIndex.value]
    if (option) select(option)
  }
}

function onClickOutside(event: PointerEvent): void {
  if (container.value && !container.value.contains(event.target as Node)) {
    open.value = false
  }
}

watch(open, async (value) => {
  if (value) {
    query.value = ''
    highlightIndex.value = Math.max(
      0,
      props.options.findIndex((option) => String(option.value) === String(props.modelValue)),
    )
    if (props.searchable) {
      await nextTick()
      searchInputRef.value?.focus()
    }
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
  <div ref="container" class="dropdown" @keydown="onKeydown">
    <button
      class="dropdown__trigger"
      type="button"
      :disabled="disabled"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="toggle"
    >
      <span class="dropdown__label">{{ selectedLabel }}</span>
      <span class="dropdown__caret" aria-hidden="true">▾</span>
    </button>

    <div v-if="open" class="dropdown__menu">
      <div v-if="searchable" class="dropdown__search">
        <input
          ref="searchInputRef"
          v-model="query"
          class="dropdown__search-input"
          type="text"
          :placeholder="searchPlaceholder"
          @input="onSearchInput"
        />
      </div>

      <div class="dropdown__options" role="listbox">
        <div v-if="filteredOptions.length === 0" class="dropdown__empty">暂无选项</div>
        <button
          v-for="(option, index) in filteredOptions"
          :key="String(option.value)"
          type="button"
          class="dropdown__option"
          :class="{
            'dropdown__option--selected': String(option.value) === String(modelValue),
            'dropdown__option--highlighted': index === highlightIndex,
          }"
          role="option"
          :aria-selected="String(option.value) === String(modelValue)"
          @mouseenter="highlightIndex = index"
          @click="select(option)"
        >
          {{ option.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dropdown {
  position: relative;
  display: inline-block;
  min-width: 120px;
  font-size: 0.85rem;
}

.dropdown__trigger {
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

.dropdown__trigger:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.dropdown__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dropdown__caret {
  font-size: 1rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.dropdown__menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  max-height: 240px;
  overflow: hidden;
  padding: 4px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.15);
}

.dropdown__search {
  flex: none;
  padding: 0 0 4px;
}

.dropdown__search-input {
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

.dropdown__search-input:focus-visible {
  outline: 2px solid var(--md-sys-color-primary, #6750a4);
  outline-offset: 1px;
}

.dropdown__options {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.dropdown__empty {
  padding: 14px 10px;
  min-width: 120px;
  text-align: center;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font-size: 0.8rem;
}

.dropdown__option {
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

.dropdown__option--highlighted {
  background: var(--md-sys-color-surface-container-highest, #e6e0e9);
}

.dropdown__option--selected {
  color: var(--md-sys-color-primary, #6750a4);
  font-weight: 600;
}
</style>
