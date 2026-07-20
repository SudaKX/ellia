<script setup lang="ts">
import { Monitor } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

const { t } = useI18n({ useScope: 'global' })

const emit = defineEmits<{
  action: [action: 'disconnect' | 'edit-ip' | 'edit-dns']
}>()

function performAction(action: 'disconnect' | 'edit-ip' | 'edit-dns') {
  emit('action', action)
}
</script>

<template>
  <section class="network-menu" :aria-label="t('network.status.ariaLabel')">
    <div class="network-menu__connection">
      <Monitor :size="28" :stroke-width="1.7" aria-hidden="true" />
      <div class="network-menu__connection-details">
        <span class="network-menu__ssid">SUDA_WIFI_5G</span>
        <span class="network-menu__state">{{ t('network.status.connected') }}</span>
      </div>
      <button class="network-menu__action" type="button" @click="performAction('disconnect')">
        {{ t('network.status.disconnect') }}
      </button>
    </div>

    <dl class="network-menu__settings">
      <div class="network-menu__setting">
        <dt>{{ t('network.status.ipAssignment') }}</dt>
        <dd>{{ t('network.status.automaticDhcp') }}</dd>
        <button class="network-menu__edit" type="button" @click="performAction('edit-ip')">
          {{ t('network.status.edit') }}
        </button>
      </div>
      <div class="network-menu__setting">
        <dt>{{ t('network.status.dnsAssignment') }}</dt>
        <dd>{{ t('network.status.automaticDhcp') }}</dd>
        <button class="network-menu__edit" type="button" @click="performAction('edit-dns')">
          {{ t('network.status.edit') }}
        </button>
      </div>
    </dl>
  </section>
</template>

<style scoped>
.network-menu {
  width: min(420px, calc(100vw - 24px));
}

.network-menu__connection {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 16px;
  color: var(--text-primary);
  border-bottom: 1px solid var(--line-subtle);
}

.network-menu__connection-details {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.network-menu__ssid,
.network-menu__state {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.network-menu__ssid {
  font: 600 13px var(--font-mono);
}

.network-menu__state {
  color: var(--signal-mint);
  font: 12px var(--font-ui);
}

.network-menu__action,
.network-menu__edit {
  min-height: 28px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: transparent;
  font: 600 11px var(--font-ui);
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.network-menu__action {
  padding: 0 10px;
}

.network-menu__edit {
  width: 52px;
}

.network-menu__action:hover {
  border-color: var(--signal-red-border);
  color: var(--signal-red-soft);
  background: var(--surface-hover);
}

.network-menu__edit:hover {
  border-color: var(--signal-mint);
  color: var(--signal-mint);
  background: var(--surface-hover);
}

.network-menu__settings {
  margin: 0;
}

.network-menu__setting {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  min-height: 54px;
  padding: 12px 16px;
}

.network-menu__setting + .network-menu__setting {
  border-top: 1px solid var(--line-subtle);
}

.network-menu__setting dt {
  color: var(--text-secondary);
  font: 12px var(--font-ui);
}

.network-menu__setting dd {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: var(--text-muted);
  font: 12px var(--font-mono);
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 420px) {
  .network-menu__connection {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .network-menu__action {
    grid-column: 2;
    justify-self: start;
  }

  .network-menu__setting {
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 6px 12px;
  }

  .network-menu__setting dd {
    text-align: right;
  }

  .network-menu__edit {
    grid-column: 2;
    justify-self: start;
  }
}
</style>
