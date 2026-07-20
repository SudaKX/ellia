<script setup lang="ts">
import { Archive, ChevronRight, FileText, LockKeyhole, Settings, TerminalSquare, X } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

import type { ApplicationId, DesktopApplication } from '@/types/desktop'

const { t } = useI18n({ useScope: 'global' })

defineProps<{
  applications: DesktopApplication[]
}>()

const emit = defineEmits<{
  close: []
}>()

const applicationIcons = {
  files: FileText,
  archive: Archive,
  terminal: TerminalSquare,
  sandbox: LockKeyhole,
  settings: Settings,
} as const

function iconFor(applicationId: ApplicationId) {
  return applicationIcons[applicationId]
}
</script>

<template>
  <section id="application-overview" class="application-overview" aria-label="Application overview">
    <div class="application-overview__head">
      <div>
        <p class="section-label">Registered modules</p>
        <h1>Applications</h1>
      </div>
      <button class="icon-button" type="button" aria-label="Close application overview" @click="emit('close')">
        <X :size="18" :stroke-width="1.8" />
      </button>
    </div>

    <div class="application-list">
      <button
        v-for="application in applications"
        :key="application.id"
        class="application-row"
        :class="{ 'application-row--locked': application.availability === 'locked' }"
        type="button"
        :disabled="application.availability === 'locked'"
      >
        <component :is="iconFor(application.id)" class="application-row__icon" :size="19" :stroke-width="1.7" />
        <span class="application-row__content">
          <span class="application-row__title">{{ t(application.nameKey) }}</span>
          <span class="application-row__description">{{ t(application.descriptionKey) }}</span>
        </span>
        <span class="application-row__group">{{ t(application.groupKey) }}</span>
        <ChevronRight class="application-row__arrow" :size="17" :stroke-width="1.7" />
      </button>
    </div>
  </section>
</template>

<style scoped>
.application-overview {
  position: absolute;
  z-index: 30;
  top: 58px;
  right: 18px;
  width: min(470px, calc(100vw - 36px));
  border: 1px solid var(--line-default);
  background: var(--surface-panel);
  box-shadow: 0 22px 56px rgba(0, 0, 0, 0.38);
}

.application-overview__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px 20px 17px;
  border-bottom: 1px solid var(--line-subtle);
}

.section-label {
  margin: 0 0 6px;
  color: var(--signal-red-soft);
  font: 700 10px var(--font-mono);
  text-transform: uppercase;
}

h1 {
  margin: 0;
  color: var(--text-primary);
  font: 600 20px var(--font-ui);
}

.icon-button {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 1px solid transparent;
  color: var(--text-muted);
  background: transparent;
}

.icon-button:hover {
  border-color: var(--line-default);
  color: var(--text-primary);
  background: var(--surface-hover);
}

.application-list {
  padding: 8px;
}

.application-row {
  display: grid;
  grid-template-columns: 34px 1fr auto 18px;
  align-items: center;
  width: 100%;
  min-height: 64px;
  gap: 11px;
  padding: 9px 10px;
  border: 1px solid transparent;
  color: inherit;
  background: transparent;
  text-align: left;
}

.application-row:hover:not(:disabled) {
  border-color: var(--line-default);
  background: var(--surface-hover);
}

.application-row__icon {
  color: var(--signal-red-soft);
}

.application-row__content {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.application-row__title {
  color: var(--text-primary);
  font: 600 13px var(--font-ui);
}

.application-row__description {
  overflow: hidden;
  color: var(--text-muted);
  font: 11px var(--font-ui);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.application-row__group {
  color: var(--text-muted);
  font: 10px var(--font-mono);
  text-transform: uppercase;
}

.application-row__arrow {
  color: var(--text-muted);
}

.application-row--locked {
  opacity: 0.48;
}

.application-row--locked .application-row__icon {
  color: var(--text-muted);
}

@media (max-width: 680px) {
  .application-overview {
    top: 54px;
    right: 12px;
    width: calc(100vw - 24px);
  }

  .application-row {
    grid-template-columns: 34px 1fr 18px;
  }

  .application-row__group {
    display: none;
  }
}
</style>
