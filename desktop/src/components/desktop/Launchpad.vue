<script setup lang="ts">
import { Archive, FileText, LockKeyhole, Settings, TerminalSquare, X } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

import type { ApplicationId, DesktopApplication } from '@/types/desktop'

const { t } = useI18n({ useScope: 'global' })

defineProps<{
  applications: DesktopApplication[]
}>()

const emit = defineEmits<{
  close: []
  launch: [applicationId: ApplicationId]
}>()

const applicationIconMap: Record<ApplicationId, typeof FileText> = {
  files: FileText,
  archive: Archive,
  terminal: TerminalSquare,
  sandbox: LockKeyhole,
  settings: Settings,
}

function iconFor(applicationId: ApplicationId) {
  return applicationIconMap[applicationId] ?? FileText
}

function handleLaunch(applicationId: ApplicationId) {
  emit('launch', applicationId)
}

function handleBackdropClick(event: MouseEvent) {
  if (event.target === event.currentTarget) {
    emit('close')
  }
}
</script>

<template>
  <div class="launchpad" role="dialog" aria-modal="true" :aria-label="t('launchpad.allApplications')" @click="handleBackdropClick">
    <div class="launchpad__panel">
      <button
        class="launchpad__close"
        type="button"
        :aria-label="t('launchpad.close')"
        @click="emit('close')"
      >
        <X :size="18" :stroke-width="1.8" />
      </button>

      <ul class="launchpad__grid">
        <li v-for="application in applications" :key="application.id">
          <button
            class="launchpad__tile"
            type="button"
            :disabled="application.availability === 'locked'"
            @click="handleLaunch(application.id)"
          >
            <span class="launchpad__tile-icon" aria-hidden="true">
              <component :is="iconFor(application.id)" :size="32" :stroke-width="1.6" />
            </span>
            <span class="launchpad__tile-name">{{ t(application.nameKey) }}</span>
            <span v-if="application.availability === 'locked'" class="launchpad__tile-badge">{{ t('common.locked') }}</span>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.launchpad {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 0 16px 88px;
  background: color-mix(in srgb, var(--canvas) 42%, transparent);
}

.launchpad__panel {
  position: relative;
  width: min(640px, 100%);
  max-height: calc(100dvh - 140px);
  overflow-y: auto;
  padding: 28px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  background: var(--surface-raised);
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.04) inset;
}

.launchpad__close {
  position: absolute;
  top: 14px;
  right: 14px;
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 0;
  color: var(--text-muted);
  background: transparent;
  transition: color 0.12s, background-color 0.12s, border-color 0.12s;
}

.launchpad__close:hover {
  border-color: var(--line-default);
  color: var(--text-primary);
  background: var(--surface-hover);
}

.launchpad__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
  gap: 16px 12px;
  margin: 0;
  padding: 12px 0 0;
  list-style: none;
}

.launchpad__tile {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 16px 8px;
  border: 1px solid transparent;
  border-radius: 0;
  color: var(--text-primary);
  background: transparent;
  text-align: center;
  transition: border-color 0.12s, background-color 0.12s;
}

.launchpad__tile:hover:not(:disabled) {
  border-color: var(--line-default);
  background: var(--surface-hover);
}

.launchpad__tile:disabled {
  opacity: 0.42;
  cursor: not-allowed;
}

.launchpad__tile-icon {
  display: grid;
  width: 56px;
  height: 56px;
  place-items: center;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--signal-red-soft);
  background: var(--surface-panel);
}

.launchpad__tile-name {
  font: 12px var(--font-ui);
  line-height: 1.2;
}

.launchpad__tile-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 5px;
  border-radius: 0;
  color: var(--text-muted);
  background: var(--surface-panel);
  font: 700 8px var(--font-mono);
  text-transform: uppercase;
}

@media (max-width: 560px) {
  .launchpad {
    padding: 0 12px 80px;
  }

  .launchpad__panel {
    padding: 24px 20px;
    border-radius: 0;
  }

  .launchpad__grid {
    grid-template-columns: repeat(auto-fill, minmax(76px, 1fr));
    gap: 12px 8px;
  }

  .launchpad__tile-icon {
    width: 48px;
    height: 48px;
  }

  .launchpad__tile-name {
    font-size: 11px;
  }
}
</style>
