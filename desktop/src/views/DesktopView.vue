<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { Activity, CircleAlert, HardDrive, Terminal } from 'lucide-vue-next'

import DesktopStatusBar from '@/components/desktop/DesktopStatusBar.vue'

const time = ref('00:00:00')
let clockTimer: number | undefined

function updateTime() {
  time.value = new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date())
}

onMounted(() => {
  updateTime()
  clockTimer = window.setInterval(updateTime, 1000)
})

onBeforeUnmount(() => {
  window.clearInterval(clockTimer)
})
</script>

<template>
  <main class="desktop-shell">
    <DesktopStatusBar :time="time" />

    <section class="desktop-workspace" aria-label="FakeOS desktop workspace">
      <div class="workspace-grid" aria-hidden="true"></div>
      <div class="signal-trace signal-trace--one" aria-hidden="true"></div>
      <div class="signal-trace signal-trace--two" aria-hidden="true"></div>

      <div class="workspace-status">
        <span class="workspace-status__line"></span>
        <span>CONSOLE READY</span>
      </div>

      <div class="session-readout">
        <p class="session-readout__eyebrow">Session</p>
        <p class="session-readout__account">PLAYER</p>
        <p class="session-readout__detail">Privilege class: LIMITED</p>
      </div>

      <aside class="system-strip" aria-label="System status">
        <div class="system-strip__item">
          <Activity :size="15" :stroke-width="1.8" />
          <span class="system-strip__label">Kernel</span>
          <strong>Stable</strong>
        </div>
        <div class="system-strip__item">
          <HardDrive :size="15" :stroke-width="1.8" />
          <span class="system-strip__label">Volume</span>
          <strong>SYS_01</strong>
        </div>
        <div class="system-strip__item system-strip__item--attention">
          <CircleAlert :size="15" :stroke-width="1.8" />
          <span class="system-strip__label">Queue</span>
          <strong>01 Event</strong>
        </div>
      </aside>

      <div class="command-hint">
        <Terminal :size="15" :stroke-width="1.8" />
        <span>Awaiting authorized process</span>
      </div>
    </section>
  </main>
</template>

<style scoped>
.desktop-shell {
  position: relative;
  display: grid;
  grid-template-rows: auto 1fr;
  min-height: 100dvh;
  overflow: hidden;
  background: var(--canvas);
}

.desktop-workspace {
  position: relative;
  min-height: 0;
  overflow: hidden;
}

.workspace-grid {
  position: absolute;
  inset: 0;
  opacity: 0.22;
  background-image: linear-gradient(var(--grid-line) 1px, transparent 1px), linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(to bottom, transparent, black 14%, black 88%, transparent);
}

.signal-trace {
  position: absolute;
  height: 1px;
  background: var(--signal-red);
  opacity: 0.78;
}

.signal-trace::after {
  position: absolute;
  top: -2px;
  right: 0;
  width: 5px;
  height: 5px;
  background: var(--signal-red);
  content: '';
}

.signal-trace--one {
  top: 25%;
  left: 0;
  width: 18%;
}

.signal-trace--two {
  right: 0;
  bottom: 19%;
  width: 12%;
  opacity: 0.34;
}

.workspace-status {
  position: absolute;
  top: 40px;
  left: 42px;
  display: flex;
  align-items: center;
  gap: 9px;
  color: var(--text-muted);
  font: 10px var(--font-mono);
}

.workspace-status__line {
  width: 20px;
  height: 1px;
  background: var(--signal-red);
}

.session-readout {
  position: absolute;
  top: 50%;
  left: 50%;
  width: min(420px, calc(100% - 64px));
  transform: translate(-50%, -50%);
  border-left: 2px solid var(--signal-red);
  padding: 20px 24px;
  background: var(--surface-quiet);
}

.session-readout__eyebrow,
.session-readout__detail {
  margin: 0;
  color: var(--text-muted);
  font: 11px var(--font-mono);
}

.session-readout__account {
  margin: 7px 0 8px;
  color: var(--text-primary);
  font: 600 32px var(--font-ui);
  letter-spacing: 0;
}

.system-strip {
  position: absolute;
  right: 42px;
  bottom: 35px;
  display: grid;
  grid-template-columns: repeat(3, minmax(104px, 1fr));
  border: 1px solid var(--line-subtle);
  background: var(--surface-raised);
}

.system-strip__item {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 8px;
  align-items: center;
  min-width: 120px;
  padding: 12px 14px;
  border-right: 1px solid var(--line-subtle);
  color: var(--signal-mint);
}

.system-strip__item:last-child {
  border-right: 0;
}

.system-strip__label {
  color: var(--text-muted);
  font: 10px var(--font-mono);
  text-transform: uppercase;
}

.system-strip strong {
  grid-column: 2;
  color: var(--text-secondary);
  font: 600 11px var(--font-ui);
}

.system-strip__item--attention {
  color: var(--signal-red-soft);
}

.command-hint {
  position: absolute;
  bottom: 40px;
  left: 42px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  font: 11px var(--font-mono);
}

@media (max-width: 780px) {
  .workspace-status {
    top: 28px;
    left: 24px;
  }

  .system-strip {
    right: 24px;
    bottom: 24px;
  }

  .command-hint {
    bottom: auto;
    top: 64px;
    left: 24px;
  }
}

@media (max-width: 560px) {
  .session-readout {
    top: 44%;
    width: calc(100% - 48px);
  }

  .system-strip {
    right: 12px;
    bottom: 12px;
    left: 12px;
    grid-template-columns: 1fr;
  }

  .system-strip__item {
    min-width: 0;
    border-right: 0;
    border-bottom: 1px solid var(--line-subtle);
  }

  .system-strip__item:last-child {
    border-bottom: 0;
  }

  .workspace-grid {
    background-size: 36px 36px;
  }
}
</style>
