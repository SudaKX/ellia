<script setup lang="ts">
import type { Component } from 'vue'

import type { ApplicationId } from '@/types/desktop'

export type DockAppState = 'minimized' | 'foreground' | 'focused'

const props = defineProps<{
  applicationId: ApplicationId
  name: string
  icon: Component
  state: DockAppState
}>()

const emit = defineEmits<{
  click: [applicationId: ApplicationId]
}>()

function handleClick() {
  emit('click', props.applicationId)
}
</script>

<template>
  <div class="dock-app-wrapper">
    <button
      class="dock-app"
      :class="`dock-app--${state}`"
      type="button"
      :aria-label="name"
      @click="handleClick"
    >
      <span class="dock-app__icon" aria-hidden="true">
        <component :is="icon" :size="22" :stroke-width="1.7" />
      </span>
      <span class="dock-app__indicator" aria-hidden="true"></span>
    </button>
    <span class="dock-tooltip" role="tooltip">{{ name }}</span>
  </div>
</template>

<style scoped>
.dock-app-wrapper {
  position: relative;
  display: flex;
  justify-content: center;
}

.dock-app {
  position: relative;
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 0;
  color: var(--text-secondary);
  background: transparent;
  transition: color 0.12s, background-color 0.12s, border-color 0.12s, transform 0.12s;
}

.dock-app:hover {
  border-color: var(--line-default);
  color: var(--text-primary);
  background: var(--surface-hover);
  transform: translateY(-2px);
}

.dock-app:active {
  transform: translateY(-1px) scale(0.96);
}

.dock-app__icon {
  display: grid;
  place-items: center;
}

.dock-app__indicator {
  position: absolute;
  bottom: 4px;
  left: 50%;
  width: 4px;
  height: 4px;
  transform: translateX(-50%);
  border-radius: 50%;
  background: var(--text-muted);
  opacity: 0.85;
  transition: background-color 0.18s ease;
}

.dock-app--focused .dock-app__indicator {
  background: var(--signal-red);
}

.dock-app--foreground .dock-app__indicator {
  background: var(--signal-mint);
}

.dock-app--minimized .dock-app__indicator {
  background: var(--text-muted);
}

.dock-tooltip {
  position: absolute;
  bottom: calc(100% + 9px);
  left: 50%;
  transform: translateX(-50%) translateY(4px);
  padding: 5px 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  background: var(--surface-panel);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  color: var(--text-primary);
  font: 11px var(--font-ui);
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.14s ease, transform 0.14s ease;
}

.dock-app-wrapper:hover .dock-tooltip {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.dock-tooltip::after {
  position: absolute;
  top: 100%;
  left: 50%;
  width: 6px;
  height: 6px;
  transform: translateX(-50%) translateY(-50%) rotate(45deg);
  border-right: 1px solid var(--line-default);
  border-bottom: 1px solid var(--line-default);
  background: var(--surface-panel);
  content: '';
}

@media (max-width: 560px) {
  .dock-app {
    width: 42px;
    height: 42px;
  }
}
</style>
