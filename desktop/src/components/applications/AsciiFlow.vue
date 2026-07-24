<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useAsciiFlow } from '@/composables/useAsciiFlow'

const DEFAULT_TEXT = `The signal emerged from the noise at 03:47 UTC — a repeating pattern buried in the carrier wave of an abandoned military satellite. At first, the intelligence community dismissed it as cosmic background radiation. Then the patterns started matching. Hexadecimal sequences that decoded into fragments of something that should not exist: a message from beyond the observable universe.

SYSTEM LOG — NODE-7 [CORRUPTED]
Attempting decryption... key rotation detected. The cipher isn't breaking — it's evolving. Each pass through the algorithm produces a different output. It's not a message. It's a conversation. And we're not the intended recipient.

Someone — or something — is listening. The satellite's telemetry shows it reoriented its antenna array at 04:12 UTC, pointing not at Earth but at a dark region between Sagittarius and Scorpius. No known stellar objects in that vector. No explanation that fits within standard physics.

The FakeOS kernel detected anomalous memory writes at address 0x7FFF_DEAD. Buffer overflow? No. The bytes are being written from inside the sandbox — an unprivileged userspace process bypassing the MMU entirely. The logs show the process name as "ellia_integrity_checker" but that process doesn't exist in the process table. It never did.

We are not alone in this system. And whatever else is here — it's been watching us since we logged in.`

const canvasRef = ref<HTMLCanvasElement | null>(null)
const statusText = ref('INITIALIZING…')

const {
  init,
  destroy,
  isDragging,
  isHovering,
  obstacleRadius,
} = useAsciiFlow({
  text: DEFAULT_TEXT,
  font: '13px "Courier New", monospace',
  lineHeight: 22,
  obstacleRadius: 80,
  loopText: true,
})

onMounted(async () => {
  if (!canvasRef.value) return
  try {
    await init(canvasRef.value)
    statusText.value = ''
  } catch (err) {
    statusText.value = `LOAD FAILED: ${err instanceof Error ? err.message : 'unknown error'}`
  }
})

onBeforeUnmount(() => {
  destroy()
})
</script>

<template>
  <div class="ascii-flow">
    <canvas
      ref="canvasRef"
      class="ascii-flow__canvas"
      :class="{
        'ascii-flow__canvas--dragging': isDragging,
        'ascii-flow__canvas--hovering': isHovering,
      }"
    ></canvas>

    <Transition name="status-fade">
      <p v-if="statusText" class="ascii-flow__status">
        <span class="ascii-flow__status-icon">◇</span>
        {{ statusText }}
      </p>
    </Transition>

    <footer class="ascii-flow__hint">
      <span class="ascii-flow__hint-icon">◈</span>
      DRAG the void &nbsp;·&nbsp; SCROLL to resize &nbsp;·&nbsp; RADIUS {{ obstacleRadius }}px
    </footer>
  </div>
</template>

<style scoped>
.ascii-flow {
  position: relative;
  display: flex;
  height: 100%;
  flex-direction: column;
  background: var(--canvas, #0d0d0f);
  overflow: hidden;
}

.ascii-flow__canvas {
  flex: 1;
  display: block;
  min-height: 0;
  cursor: default;
}

.ascii-flow__canvas--hovering {
  cursor: grab;
}

.ascii-flow__canvas--dragging {
  cursor: grabbing;
}

.ascii-flow__status {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  margin: 0;
  color: var(--signal-red-soft, #c83232);
  font: 13px var(--font-mono, "Courier New", monospace);
  letter-spacing: 2px;
  text-transform: uppercase;
  pointer-events: none;
}

.ascii-flow__status-icon {
  margin-right: 8px;
  opacity: 0.6;
}

.status-fade-enter-active,
.status-fade-leave-active {
  transition: opacity 0.3s ease;
}

.status-fade-enter-from,
.status-fade-leave-to {
  opacity: 0;
}

.ascii-flow__hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 28px;
  padding: 0 12px;
  border-top: 1px solid var(--line-subtle, rgba(255, 255, 255, 0.05));
  color: var(--text-muted, #666);
  font: 11px var(--font-mono, "Courier New", monospace);
  letter-spacing: 0.5px;
  background: var(--surface-panel, #111);
  user-select: none;
}

.ascii-flow__hint-icon {
  color: var(--signal-red-soft, #c83232);
  font-size: 10px;
}
</style>
