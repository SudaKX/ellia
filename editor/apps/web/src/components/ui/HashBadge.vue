<script setup lang="ts">
import { computed } from 'vue'

import { getHashColorPair } from '../../utils/color'

const props = defineProps<{
  value: string
}>()

const colors = computed(() => getHashColorPair(props.value))
</script>

<template>
  <span
    class="hash-badge"
    :style="{ backgroundColor: colors.background, color: colors.color }"
  >
    <slot>{{ value }}</slot>
  </span>
</template>

<style scoped>
.hash-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  white-space: nowrap;
}
</style>