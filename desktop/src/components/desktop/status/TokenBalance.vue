<script setup lang="ts">
/**
 * # 代币钱包胶囊（状态栏）
 *
 * 常驻展示当前代币余额，符号按界面语言本地化（见 `@/registries/currencies`）：
 * zh-CN ¥ / zh-TW NT$ / ja-JP ¥ / en-US $ / de-DE € / binary ₿
 *
 * 点击展开钱包面板：显示余额、展示货币与刷新入口。
 * 交互与 StatusMenuButton 一致：点击外部区域关闭。
 */

import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { RefreshCw, Wallet } from 'lucide-vue-next'

import { formatTokenAmount, formatTokenNumber, getCurrency } from '@/registries/currencies'
import { useCreditsStore } from '@/stores/credits'

const { t, locale } = useI18n({ useScope: 'global' })
const credits = useCreditsStore()

const isOpen = ref(false)
const rootRef = ref<HTMLDivElement | null>(null)

const currency = computed(() => getCurrency(locale.value))

/** 胶囊上的余额数字（符号由旁边的 symbol span 展示，避免符号重复） */
const displayBalance = computed(() => {
  if (credits.isLoading && !credits.isLoaded) return '···'
  if (!credits.isLoaded) return credits.error ? '—' : '···'
  return formatTokenNumber(credits.vtb, locale.value)
})

function toggle() {
  isOpen.value = !isOpen.value
}

function close() {
  isOpen.value = false
}

function handleClickOutside(event: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(event.target as Node)) {
    close()
  }
}

async function refresh() {
  await credits.fetchBalances()
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div ref="rootRef" class="token-balance">
    <button
      class="token-balance__trigger"
      :class="{ 'token-balance__trigger--active': isOpen }"
      type="button"
      :aria-label="t('tokens.label')"
      :aria-expanded="isOpen"
      :title="t('tokens.label')"
      @click.stop="toggle"
    >
      <span class="token-balance__symbol">{{ currency.symbol }}</span>
      <span class="token-balance__amount">{{ displayBalance }}</span>
    </button>

    <div
      v-if="isOpen"
      class="token-balance__panel"
      role="dialog"
      :aria-label="t('tokens.label')"
      @click.stop
    >
      <div class="menu-header">
        <Wallet :size="14" :stroke-width="1.8" />
        <span class="menu-title">{{ t('tokens.label') }}</span>
      </div>

      <div class="menu-body">
        <div class="token-row">
          <span>{{ t('tokens.vtb') }}</span>
          <span class="token-row__value">{{ formatTokenAmount(credits.vtb, locale) }}</span>
        </div>

        <p v-if="credits.error" class="token-balance__error">
          {{ t('tokens.error') }}
          <code>{{ credits.error }}</code>
        </p>

        <button
          class="menu-item"
          type="button"
          :disabled="credits.isLoading"
          @click="refresh"
        >
          <RefreshCw
            :size="14"
            :stroke-width="1.5"
            :class="{ 'is-spinning': credits.isLoading }"
          />
          <span>{{ t('tokens.refresh') }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.token-balance {
  position: relative;
}

.token-balance__trigger {
  display: flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 0;
  color: var(--text-secondary);
  background: transparent;
  font-family: var(--font-mono);
  font-size: 12px;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.token-balance__trigger:hover,
.token-balance__trigger--active {
  border-color: var(--line-default);
  color: var(--signal-red-soft);
  background: var(--surface-hover);
}

.token-balance__symbol {
  color: var(--text-tertiary);
  font-weight: 700;
}

.token-balance__amount {
  font-weight: 600;
}

.token-balance__panel {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 40;
  min-width: 220px;
  border: 1px solid var(--line-default);
  background: var(--surface-panel);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4);
}

.menu-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 12px 12px 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line-subtle);
  color: var(--text-secondary);
}

.menu-title {
  color: var(--text-primary);
  font: 600 12px var(--font-ui);
}

.menu-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0 12px 12px;
}

.token-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 0;
  color: var(--text-primary);
  font: 400 12px var(--font-ui);
}

.token-row__value {
  font-family: var(--font-mono);
  font-weight: 700;
}

.token-row--muted {
  padding-top: 0;
  color: var(--text-secondary);
  font-size: 11px;
}

.token-balance__error {
  margin: 6px 0 2px;
  color: var(--signal-red-soft);
  font: 400 11px var(--font-ui);
}

.token-balance__error code {
  display: block;
  margin-top: 2px;
  overflow-wrap: anywhere;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 10px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px;
  border: none;
  color: var(--text-primary);
  background: transparent;
  font: 400 12px var(--font-ui);
  text-align: left;
  cursor: pointer;
}

.menu-item:hover:not(:disabled) {
  background: var(--surface-hover);
}

.menu-item:disabled {
  opacity: 0.55;
  cursor: default;
}

.is-spinning {
  animation: token-balance-spin 0.8s linear infinite;
}

@keyframes token-balance-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
