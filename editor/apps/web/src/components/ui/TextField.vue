<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    disabled?: boolean
    type?: string
    /** 推荐候选；为空时不显示下拉，退化为普通输入框 */
    recommends?: string[]
  }>(),
  {
    placeholder: '',
    disabled: false,
    type: 'text',
    recommends: () => [],
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const container = ref<HTMLElement | null>(null)
const open = ref(false)
const highlightIndex = ref(-1)

const hasRecommends = computed(() => props.recommends.length > 0)

const filteredRecommends = computed(() => {
  const query = props.modelValue.trim().toLowerCase()
  if (!query) return props.recommends
  return props.recommends.filter((item) => item.toLowerCase().includes(query))
})

const showMenu = computed(() => hasRecommends.value && open.value)

function onInput(event: Event): void {
  const value = (event.target as HTMLInputElement).value
  emit('update:modelValue', value)
  if (hasRecommends.value) {
    open.value = true
    highlightIndex.value = -1
  }
}

function onFocus(): void {
  if (hasRecommends.value) open.value = true
}

function selectRecommend(value: string): void {
  emit('update:modelValue', value)
  open.value = false
  highlightIndex.value = -1
}

function onKeydown(event: KeyboardEvent): void {
  if (props.disabled || !hasRecommends.value) return

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
    highlightIndex.value = Math.min(filteredRecommends.value.length - 1, highlightIndex.value + 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    highlightIndex.value = Math.max(0, highlightIndex.value - 1)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const option = filteredRecommends.value[highlightIndex.value]
    if (option !== undefined) {
      selectRecommend(option)
    } else {
      open.value = false
    }
  } else if (event.key === 'Home') {
    highlightIndex.value = 0
  } else if (event.key === 'End') {
    highlightIndex.value = filteredRecommends.value.length - 1
  }
}

function onClickOutside(event: PointerEvent): void {
  if (container.value && !container.value.contains(event.target as Node)) {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('pointerdown', onClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onClickOutside)
})
</script>

<template>
  <div ref="container" class="text-field-combo" @keydown="onKeydown">
    <input
      class="text-field"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="onInput"
      @focus="onFocus"
    />

    <div v-if="showMenu" class="text-field-combo__menu" role="listbox">
      <div v-if="filteredRecommends.length === 0" class="text-field-combo__empty">
        无匹配推荐
      </div>
      <button
        v-for="(option, index) in filteredRecommends"
        :key="option"
        type="button"
        class="text-field-combo__option"
        :class="{ 'text-field-combo__option--highlighted': index === highlightIndex }"
        role="option"
        :aria-selected="option === modelValue"
        @mouseenter="highlightIndex = index"
        @click="selectRecommend(option)"
      >
        {{ option }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.text-field-combo {
  position: relative;
  width: 100%;
}

.text-field {
  width: 100%;
  min-height: 32px;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
  font-size: 0.85rem;
}

.text-field:focus-visible {
  outline: 2px solid var(--md-sys-color-primary, #6750a4);
  outline-offset: 1px;
}

.text-field:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.text-field-combo__menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 30;
  max-height: 240px;
  overflow-y: auto;
  padding: 4px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.15);
}

.text-field-combo__empty {
  padding: 14px 10px;
  min-width: 120px;
  text-align: center;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font-size: 0.8rem;
}

.text-field-combo__option {
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

.text-field-combo__option--highlighted {
  background: var(--md-sys-color-surface-container-highest, #e6e0e9);
}
</style>
