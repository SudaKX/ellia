<script setup lang="ts">
import { computed } from 'vue'

import type { PresenceUser } from '@ellia/puzzle-schema'

import { getHashColorPair } from '../../utils/color'

const props = defineProps<{
  user: PresenceUser
}>()

const colors = computed(() => getHashColorPair(props.user.username))
</script>

<template>
  <span
    class="user-badge"
    :style="{ backgroundColor: colors.background, color: colors.color }"
    :title="user.username"
  >
    {{ user.username.slice(0, 2).toUpperCase() }}
  </span>
</template>

<style scoped>
.user-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  user-select: none;
  flex: none;
}
</style>