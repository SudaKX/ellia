<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import UserBadge from '../presence/UserBadge.vue'
import { useEditorTabsStore } from '../../stores/editorTabs'
import { useEntitiesStore } from '../../stores/entities'
import { usePresenceStore } from '../../stores/presence'
import EntityCard from './EntityCard.vue'
import EntityFilterBar from './EntityFilterBar.vue'

const entitiesStore = useEntitiesStore()
const tabsStore = useEditorTabsStore()
const presenceStore = usePresenceStore()
const router = useRouter()

const filters = ref<{ kind: string; group: string }>({ kind: '', group: '' })
const menuOpen = ref(false)
const menuContainer = ref<HTMLElement | null>(null)

const kinds = computed(() => [...new Set(entitiesStore.entityList.map((entity) => entity.kind))].sort())
const groups = computed(() => [...new Set(entitiesStore.entityList.map((entity) => entity.group))].sort())

const filteredEntities = computed(() =>
  entitiesStore.entityList.filter((entity) => {
    if (filters.value.kind && entity.kind !== filters.value.kind) return false
    if (filters.value.group && entity.group !== filters.value.group) return false
    return true
  }),
)

function openEntity(entity: (typeof filteredEntities.value)[number]): void {
  tabsStore.openTab(entity)
}

function toggleMenu(): void {
  menuOpen.value = !menuOpen.value
}

function goHome(): void {
  menuOpen.value = false
  void router.push('/')
}

function onClickOutside(event: PointerEvent): void {
  if (menuContainer.value && !menuContainer.value.contains(event.target as Node)) {
    menuOpen.value = false
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
  <div class="entity-browser">
    <EntityFilterBar v-model="filters" :kinds="kinds" :groups="groups" />

    <div class="entity-browser__content">
      <div v-if="filteredEntities.length === 0" class="entity-browser__empty">
        {{ entitiesStore.entityList.length === 0 ? '这个项目还没有实体' : '没有符合筛选条件的实体' }}
      </div>
      <div v-else class="entity-browser__cards">
        <EntityCard
          v-for="entity in filteredEntities"
          :key="entity.id"
          :entity="entity"
          :users="presenceStore.usersByEntity[entity.id] ?? []"
          @open="openEntity"
        />
      </div>
    </div>

    <div ref="menuContainer" class="entity-browser__footer">
      <button
        class="entity-browser__menu-button"
        type="button"
        aria-label="菜单"
        aria-haspopup="menu"
        :aria-expanded="menuOpen"
        @click="toggleMenu"
      >
        ⋯
      </button>

      <div v-if="menuOpen" class="entity-browser__menu" role="menu">
        <button class="entity-browser__menu-item" type="button" role="menuitem" @click="goHome">
          返回项目界面
        </button>
      </div>

      <div class="entity-browser__online" :title="`${presenceStore.users.length} 人在线`">
        <UserBadge v-for="user in presenceStore.users" :key="user.id" :user="user" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.entity-browser {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
}

.entity-browser__content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.entity-browser__cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
  padding: 8px;
  align-content: start;
}

.entity-browser__empty {
  padding: 24px;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  text-align: center;
}

.entity-browser__footer {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  flex: none;
  min-height: 40px;
  padding: 4px 8px;
  border-top: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
}

.entity-browser__menu-button {
  flex: none;
  width: 28px;
  height: 28px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 999px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  color: var(--md-sys-color-on-surface, #1d1b20);
  cursor: pointer;
  line-height: 1;
}

.entity-browser__menu-button:hover {
  background: var(--md-sys-color-surface-container-highest, #e6e0e9);
}

.entity-browser__menu {
  position: absolute;
  left: 8px;
  bottom: calc(100% + 4px);
  z-index: 20;
  min-width: 160px;
  padding: 4px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.15);
}

.entity-browser__menu-item {
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

.entity-browser__menu-item:hover {
  background: var(--md-sys-color-surface-container-highest, #e6e0e9);
}

.entity-browser__online {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 2px 0;
}
</style>