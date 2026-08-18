<script setup lang="ts">
import { computed } from 'vue'

import { useAuthStore } from '../../stores/auth'
import { useLocksStore } from '../../stores/locks'

const props = defineProps<{
  entityId: string
  dataPath: string
}>()

const auth = useAuthStore()
const locks = useLocksStore()

const holder = computed(() => locks.holderOf(props.dataPath))
const isSelf = computed(() => holder.value?.holder.id === auth.user?.id)
</script>

<template>
  <div v-if="holder" class="lock-hint" :class="{ 'lock-hint--self': isSelf }">
    <span class="lock-hint__icon">🔒</span>
    <span>
      {{ isSelf ? '你正在编辑' : `${holder.holder.username} 正在编辑` }}
      <code>{{ dataPath }}</code>
    </span>
  </div>
</template>

<style scoped>
.lock-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 999px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  font-size: 0.75rem;
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.lock-hint--self {
  border-color: var(--md-sys-color-primary, #6750a4);
  background: var(--md-sys-color-primary-container, #eaddff);
}

.lock-hint__icon {
  font-size: 0.85rem;
}

code {
  font-size: 0.7rem;
}
</style>