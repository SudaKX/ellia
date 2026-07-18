<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps<{
  menuId: string
  label: string
  icon: unknown
  activeMenuId: string | null
}>()

const emit = defineEmits<{
  setActive: [menuId: string | null]
}>()

const isOpen = computed(() => props.activeMenuId === props.menuId)
const rootRef = ref<HTMLDivElement | null>(null)

function toggle() {
  emit('setActive', isOpen.value ? null : props.menuId)
}

function close() {
  if (isOpen.value) {
    emit('setActive', null)
  }
}

function handleClickOutside(event: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(event.target as Node)) {
    close()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div ref="rootRef" class="status-menu">
    <button
      class="status-menu__trigger"
      :class="{ 'status-menu__trigger--active': isOpen }"
      type="button"
      :aria-label="label"
      :aria-expanded="isOpen"
      @click.stop="toggle"
    >
      <component :is="icon" :size="17" :stroke-width="1.8" />
    </button>

    <div v-if="isOpen" class="status-menu__panel" role="dialog" :aria-label="label" @click.stop>
      <slot />
    </div>
  </div>
</template>

<style scoped>
.status-menu {
  position: relative;
}

.status-menu__trigger {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--text-secondary);
  background: transparent;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.status-menu__trigger:hover,
.status-menu__trigger--active {
  border-color: var(--line-default);
  color: var(--signal-red-soft);
  background: var(--surface-hover);
}

.status-menu__panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 40;
  min-width: 200px;
  border: 1px solid var(--line-default);
  background: var(--surface-panel);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4);
}
</style>
