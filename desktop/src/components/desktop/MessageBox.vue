<script setup lang="ts">
/**
 * # 消息弹窗组件（模态窗口内容）
 *
 * 通用的模态弹窗内容容器。支持两种内容模式：
 * - **文本模式**：传入 `message` 字符串
 * - **组件模式**：传入 `contentComponent`（如 PermissionDenied），可带 `contentProps`
 *
 * ## 使用场景
 *
 * 当前主要用于网络菜单操作后的"权限拒绝"反馈。
 * DesktopView.handleNetworkAction() 通过 windowService.send 创建模态窗口，
 * 其内容组件为此 MessageBox + PermissionDenied。
 *
 * ## 与 darksky 分支区别
 *
 * darksky 分支移除了此组件。保留它是因为模态弹窗
 * 是 FakeOS 叙事表达的核心载体——"看起来能用但实际没权限"的体验。
 */

import type { Component } from 'vue'
import { useI18n } from 'vue-i18n'

interface MessageBoxAction {
  labelKey: string
  tone?: 'default' | 'danger'
}

const { t } = useI18n({ useScope: 'global' })

const props = withDefaults(
  defineProps<{
    message?: string
    contentComponent?: Component
    contentProps?: Record<string, unknown>
    actions?: MessageBoxAction[]
  }>(),
  {
    message: '',
    contentProps: () => ({}),
    actions: () => [{ labelKey: 'common.close' }],
  },
)

const emit = defineEmits<{
  close: []
}>()

function handleAction() {
  emit('close')
}
</script>

<template>
  <section class="message-box" aria-live="polite">
    <div class="message-box__content">
      <component v-if="props.contentComponent" :is="props.contentComponent" v-bind="props.contentProps" />
      <p v-else class="message-box__message">{{ props.message }}</p>
    </div>

    <footer class="message-box__actions">
      <button
        v-for="action in props.actions"
        :key="action.labelKey"
        class="message-box__action"
        :class="{ 'message-box__action--danger': action.tone === 'danger' }"
        type="button"
        @click="handleAction"
      >
        {{ t(action.labelKey) }}
      </button>
    </footer>
  </section>
</template>

<style scoped>
.message-box {
  display: grid;
  min-height: 100%;
  grid-template-rows: minmax(0, 1fr) auto;
}

.message-box__content {
  display: grid;
  min-height: 0;
  place-items: center;
  padding: 24px;
  color: var(--text-secondary);
  text-align: center;
}

.message-box__message {
  max-width: 40ch;
  margin: 0;
  font: 13px/1.55 var(--font-ui);
}

.message-box__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--line-subtle);
}

.message-box__action {
  min-width: 96px;
  min-height: 32px;
  padding: 0 14px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: transparent;
  font: 600 11px var(--font-ui);
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.message-box__action:hover {
  border-color: var(--signal-mint);
  color: var(--signal-mint);
  background: var(--surface-hover);
}

.message-box__action--danger:hover {
  border-color: var(--signal-red-border);
  color: var(--signal-red-soft);
}
</style>
