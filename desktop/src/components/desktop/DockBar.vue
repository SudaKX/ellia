<script setup lang="ts">
import { ChevronUp, CircleDashed, LayoutGrid } from 'lucide-vue-next'

import DockApp from './DockApp.vue'
import { applicationRegistry } from '@/registries/applications'
import type { ApplicationId } from '@/types/desktop'

export type DockAppState = 'minimized' | 'foreground' | 'focused'

export interface DockApplicationState {
  applicationId: ApplicationId
  name: string
  state: DockAppState
}

const props = defineProps<{
  applicationStates: DockApplicationState[]
}>()

const emit = defineEmits<{
  click: [applicationId: ApplicationId]
  showAll: []
}>()

function iconFor(applicationId: ApplicationId) {
  return applicationRegistry[applicationId].icon
}
</script>

<template>
  <nav class="dock-bar" aria-label="Application dock">
    <div class="dock-bar__track">
      <ul class="dock-bar__apps" aria-label="Open applications">
        <li
          v-for="application in applicationStates"
          :key="application.applicationId"
          class="dock-bar__apps-item"
        >
          <DockApp
            :application-id="application.applicationId"
            :name="application.name"
            :icon="iconFor(application.applicationId)"
            :state="application.state"
            @click="emit('click', application.applicationId)"
          />
        </li>
        <li v-if="applicationStates.length === 0" class="dock-bar__apps-item">
          <span class="dock-app-placeholder" aria-hidden="true">
            <CircleDashed :size="22" :stroke-width="1.7" />
          </span>
        </li>
      </ul>

      <span class="dock-bar__divider" aria-hidden="true"></span>

      <div class="dock-bar__item">
        <button
          class="dock-bar__launcher"
          type="button"
          aria-label="Show all applications"
          @click="emit('showAll')"
        >
          <LayoutGrid :size="20" :stroke-width="1.8" />
          <ChevronUp class="dock-bar__launcher-chevron" :size="12" :stroke-width="1.8" />
        </button>
        <span class="dock-tooltip" role="tooltip">All Applications</span>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.dock-bar {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 100;
  display: flex;
  justify-content: center;
  padding: 0 16px calc(16px + env(safe-area-inset-bottom, 0px));
  pointer-events: none;
}

.dock-bar__track {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 9px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  background: var(--surface-raised);
  box-shadow: 0 14px 44px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.03) inset;
  pointer-events: auto;
}

.dock-bar__apps {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-width: 46px;
  min-height: 46px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.dock-bar__apps-item {
  display: flex;
  align-items: center;
  justify-content: center;
}

.dock-app-placeholder {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  color: var(--text-muted);
  opacity: 0.35;
}

.dock-bar__divider {
  width: 1px;
  height: 28px;
  background: var(--line-subtle);
}

.dock-bar__launcher {
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

.dock-bar__launcher:hover {
  border-color: var(--line-default);
  color: var(--signal-red-soft);
  background: var(--surface-hover);
  transform: translateY(-2px);
}

.dock-bar__launcher:active {
  transform: translateY(-1px) scale(0.96);
}

.dock-bar__launcher-chevron {
  position: absolute;
  bottom: 6px;
  opacity: 0;
  transition: opacity 0.12s, transform 0.12s;
  transform: translateY(2px);
}

.dock-bar__launcher:hover .dock-bar__launcher-chevron {
  opacity: 1;
  transform: translateY(0);
}

.dock-bar__item {
  position: relative;
  display: flex;
  justify-content: center;
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

.dock-bar__item:hover .dock-tooltip {
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
  .dock-bar {
    padding: 0 12px calc(12px + env(safe-area-inset-bottom, 0px));
  }

  .dock-bar__track {
    padding: 6px 8px;
    border-radius: 0;
  }

  .dock-app-placeholder,
  .dock-bar__launcher {
    width: 42px;
    height: 42px;
  }

  .dock-bar__apps {
    min-width: 42px;
    min-height: 42px;
  }
}
</style>
