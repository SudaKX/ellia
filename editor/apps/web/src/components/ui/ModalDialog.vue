<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    confirmLabel?: string
    cancelLabel?: string
    showCancel?: boolean
    danger?: boolean
    busy?: boolean
    confirmDisabled?: boolean
  }>(),
  {
    confirmLabel: '确认',
    cancelLabel: '取消',
    showCancel: true,
    danger: false,
    busy: false,
    confirmDisabled: false,
  },
)

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const dialogRef = ref<HTMLElement | null>(null)

/** 按下和松开都在弹窗内容之外才关闭 */
let downOnDialog = false

function onOverlayPointerDown(event: PointerEvent): void {
  downOnDialog = dialogRef.value?.contains(event.target as Node) ?? false
}

function onOverlayPointerUp(event: PointerEvent): void {
  if (props.busy) return
  // 如果鼠标离开浏览器窗口，release 事件的 target 可能是 document.body 等，不触发关闭
  if (!event.target || !(event.target instanceof Node)) return
  const upOnDialog = dialogRef.value?.contains(event.target as Node) ?? false
  if (!downOnDialog && !upOnDialog) {
    emit('cancel')
  }
}

onBeforeUnmount(() => {
  downOnDialog = false
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="modal-overlay"
      @pointerdown="onOverlayPointerDown"
      @pointerup="onOverlayPointerUp"
    >
      <div
        ref="dialogRef"
        class="modal-dialog"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        @click.stop
      >
        <header class="modal-dialog__header">
          <h3>{{ title }}</h3>
        </header>

        <div class="modal-dialog__body">
          <slot />
        </div>

        <footer v-if="showCancel || confirmLabel" class="modal-dialog__footer">
          <button
            v-if="showCancel"
            class="btn btn--text"
            type="button"
            :disabled="busy"
            @click="emit('cancel')"
          >
            {{ cancelLabel }}
          </button>
          <button
            class="btn"
            :class="danger ? 'btn--danger' : 'btn--primary'"
            type="button"
            :disabled="busy || confirmDisabled"
            @click="emit('confirm')"
          >
            {{ confirmLabel }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  background: rgb(0 0 0 / 0.4);
  padding: 1rem;
}

.modal-dialog {
  width: min(420px, 100%);
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  color: var(--md-sys-color-on-surface, #1d1b20);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgb(0 0 0 / 0.25);
  overflow: hidden;
}

.modal-dialog__header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
}

.modal-dialog__header h3 {
  margin: 0;
  font-size: 1rem;
}

.modal-dialog__body {
  padding: 16px;
}

.modal-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
}
</style>