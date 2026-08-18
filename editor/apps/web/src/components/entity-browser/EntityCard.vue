<script setup lang="ts">
import type { EntityRecord, PresenceUser } from '@ellia/puzzle-schema'

import HashBadge from '../ui/HashBadge.vue'
import UserBadge from '../presence/UserBadge.vue'

defineProps<{
  entity: EntityRecord
  users: PresenceUser[]
}>()

const emit = defineEmits<{
  (e: 'open', entity: EntityRecord): void
}>()
</script>

<template>
  <button class="entity-card" type="button" @click="emit('open', entity)">
    <div class="entity-card__title">{{ entity.resource_id }}</div>
    <div class="entity-card__meta">
      <HashBadge :value="entity.kind" />
      <span class="badge badge--secondary">{{ entity.group }}</span>
    </div>
    <div
      class="entity-card__presence"
      :title="users.length > 0 ? '正在编辑此实体的用户' : undefined"
    >
      <UserBadge v-for="user in users" :key="user.id" :user="user" />
      <span
        v-if="users.length === 0"
        class="entity-card__presence-placeholder"
        aria-label="无人编辑"
      />
    </div>
  </button>
</template>

<style scoped>
.entity-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
  text-align: left;
  padding: 10px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
  color: var(--md-sys-color-on-surface, #1d1b20);
  cursor: pointer;
  min-width: 0;
}

.entity-card:hover {
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.entity-card__title {
  font-weight: 600;
  font-size: 0.9rem;
  word-break: break-all;
  width: 100%;
}

.entity-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 999px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.entity-card__presence {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 24px;
}

.entity-card__presence-placeholder {
  width: 24px;
  height: 24px;
  border: 1px dashed var(--md-sys-color-outline, #79747e);
  border-radius: 999px;
  box-sizing: border-box;
}
</style>