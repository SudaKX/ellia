<script setup lang="ts">
import { computed } from 'vue'

import { getHashColorPair } from '../../utils/color'

const props = withDefaults(
  defineProps<{
    username: string
    block?: boolean
  }>(),
  {
    block: true,
  },
)

const colors = computed(() => getHashColorPair(props.username))
</script>

<template>
  <div
    class="lock-overlay"
    :class="{ 'lock-overlay--non-blocking': !block }"
    :style="{ borderColor: colors.background }"
  >
    <div
      class="lock-overlay__tag"
      :style="{
        borderColor: colors.background,
        background: colors.background,
        color: colors.color,
      }"
    >
      <span>{{ username }}</span>
    </div>
  </div>
</template>

<style scoped>
.lock-overlay {
  position: absolute;
  inset: 0;
  z-index: 100;
  padding: 0;
  border: 2px solid transparent;
  border-radius: 8px;
  pointer-events: auto;
  cursor: not-allowed;
  backdrop-filter: brightness(0.6);
}

.lock-overlay--non-blocking {
  pointer-events: none;
  cursor: default;
  backdrop-filter: none;
}

.lock-overlay__tag {
  position: absolute;
  right: 0;
  bottom: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: calc(100% - 12px);
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 8px 0 8px 0;
  translate: 2px 2px;
  font-size: 0.7rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>