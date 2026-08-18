<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import type { EntityRecord } from '@ellia/puzzle-schema'

import { syncClient } from '../../../../client/ws'
import { useAuthStore } from '../../../../stores/auth'
import { useLocksStore } from '../../../../stores/locks'
import { usePresenceStore } from '../../../../stores/presence'
import UserBadge from '../../../presence/UserBadge.vue'
import { getHashColorPair } from '../../../../utils/color'
import FieldEditDialog from './FieldEditDialog.vue'
import type { FieldSpec } from './formTypes'
import ObjectField from './ObjectField.vue'

const props = defineProps<{
  entity: EntityRecord
  fieldName: string
  fieldSpec: FieldSpec
  dataPath: string
  modelValue: unknown
}>()

const auth = useAuthStore()
const locks = useLocksStore()
const presence = usePresenceStore()

const lockInfo = computed(() => locks.holderOf(props.dataPath))
const lockedByOther = computed(() => Boolean(lockInfo.value && lockInfo.value.holder.id !== auth.user?.id))
const holderColor = computed(() =>
  lockInfo.value ? getHashColorPair(lockInfo.value.holder.username) : { background: '#000000', color: '#ffffff' },
)
const fieldPresence = computed(() => presence.userAtPath(props.entity.id, props.dataPath))
const isNonObject = computed(() => props.fieldSpec.type !== 'object')

const displayValue = computed(() => {
  const value = props.modelValue
  switch (props.fieldSpec.type) {
    case 'bool':
      return value ? '是' : '否'
    case 'array':
      return Array.isArray(value) ? `${value.length} 项` : '（空）'
    case 'string':
    case 'number':
      return value === undefined || value === null || value === '' ? '（空）' : String(value)
    default:
      return ''
  }
})

const fullValueText = computed(() => {
  const value = props.modelValue
  switch (props.fieldSpec.type) {
    case 'bool':
      return value ? '是' : '否'
    case 'array':
      return Array.isArray(value) ? JSON.stringify(value, null, 2) : '（空）'
    case 'string':
    case 'number':
      return value === undefined || value === null || value === '' ? '（空）' : String(value)
    default:
      return ''
  }
})

const tooltipVisible = ref(false)
let tooltipTimer: ReturnType<typeof setTimeout> | null = null

function onValueMouseEnter(): void {
  if (tooltipTimer) clearTimeout(tooltipTimer)
  tooltipTimer = setTimeout(() => {
    tooltipVisible.value = true
  }, 500)
}

function onValueMouseLeave(): void {
  if (tooltipTimer) clearTimeout(tooltipTimer)
  tooltipTimer = null
  tooltipVisible.value = false
}

onBeforeUnmount(() => {
  if (tooltipTimer) clearTimeout(tooltipTimer)
})

const valueRef = ref<HTMLButtonElement | null>(null)

function triggerBlink(): void {
  const element = valueRef.value
  if (!element) return

  const rootStyle = getComputedStyle(document.documentElement)
  const primary = rootStyle.getPropertyValue('--md-sys-color-primary').trim() || '#6750a4'
  const onPrimary = rootStyle.getPropertyValue('--md-sys-color-on-primary').trim() || '#ffffff'

  const currentStyle = getComputedStyle(element)
  const currentBackground = currentStyle.backgroundColor
  const currentColor = currentStyle.color
  const currentBorder = currentStyle.borderColor

  // 取消上一次未完成的闪烁动画，避免叠加
  element.getAnimations().forEach((animation) => animation.cancel())

  element.animate(
    [
      {
        backgroundColor: primary,
        color: onPrimary,
        borderColor: primary,
      },
      {
        backgroundColor: currentBackground,
        color: currentColor,
        borderColor: currentBorder,
      },
    ],
    {
      duration: 300,
      easing: 'ease',
    },
  )
}

watch(
  () => props.modelValue,
  (newValue, oldValue) => {
    if (newValue === oldValue) return
    triggerBlink()
  },
)

const dialogOpen = ref(false)
const dialogLocked = ref(false)
const busy = ref(false)
const error = ref<string | null>(null)

async function openDialog(): Promise<void> {
  if (lockedByOther.value) return
  busy.value = true
  error.value = null
  try {
    await syncClient.lock(props.entity.id, props.dataPath)
    dialogLocked.value = true
    dialogOpen.value = true
  } catch (err) {
    error.value = err instanceof Error ? err.message : '无法获取编辑锁'
  } finally {
    busy.value = false
  }
}

async function confirmDialog(value: unknown): Promise<void> {
  busy.value = true
  error.value = null
  let succeeded = false
  try {
    await syncClient.patch(props.entity.id, props.dataPath, value)
    succeeded = true
    dialogOpen.value = false
  } catch (err) {
    error.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    // patch 成功后服务端会自动释放锁；失败时服务端通常也会释放。
    // 只有在未成功时才尝试补一次 unlock，且不等待结果，避免界面卡在 busy。
    if (dialogLocked.value && !succeeded) {
      syncClient.unlock(props.entity.id, props.dataPath).catch(() => undefined)
    }
    dialogLocked.value = false
    busy.value = false
  }
}

async function cancelDialog(): Promise<void> {
  dialogOpen.value = false
  if (dialogLocked.value) {
    await syncClient.unlock(props.entity.id, props.dataPath).catch(() => undefined)
    dialogLocked.value = false
  }
}
</script>

<template>
  <div class="form-field">
    <div class="form-field__main">
      <div class="form-field__info">
        <div class="form-field__header">
          <span class="form-field__label">{{ fieldName }}</span>

          <UserBadge v-for="user in fieldPresence" :key="user.id" :user="user" />
        </div>
        <p v-if="fieldSpec.description" class="form-field__description">
          {{ fieldSpec.description }}
        </p>
      </div>

      <div v-if="isNonObject" class="form-field__value-wrap">
        <button
          ref="valueRef"
          class="form-field__value"
          type="button"
          :disabled="lockedByOther || busy"
          @click="openDialog"
          @mouseenter="onValueMouseEnter"
          @mouseleave="onValueMouseLeave"
        >
          {{ displayValue }}
        </button>
        <div v-if="tooltipVisible" class="form-field__tooltip">
          {{ fullValueText }}
        </div>
      </div>
    </div>

    <div
      v-if="lockInfo"
      class="form-field__lock-overlay"
      :style="{ borderColor: holderColor.background }"
    >
      <div
        class="form-field__lock-tag"
        :style="{
          borderColor: holderColor.background,
          background: holderColor.background,
          color: holderColor.color,
        }"
      >
        <span>{{ lockInfo.holder.username }}</span>
      </div>
    </div>

    <span v-if="error" class="error-text" role="alert">{{ error }}</span>

    <ObjectField
      v-if="!isNonObject"
      :entity="entity"
      :field-spec="fieldSpec"
      :data-path="dataPath"
      :model-value="modelValue"
    />

    <FieldEditDialog
      v-if="isNonObject"
      :open="dialogOpen"
      :entity="entity"
      :field-spec="fieldSpec"
      :data-path="dataPath"
      :model-value="modelValue"
      @confirm="confirmDialog"
      @cancel="cancelDialog"
    />
  </div>
</template>

<style scoped>
.form-field {
  position: relative;
  display: grid;
  gap: 6px;
  padding: 8px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
}

.form-field__lock-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  padding: 0;
  border: 2px solid transparent;
  border-radius: 8px;
  pointer-events: auto;
  cursor: not-allowed;
  backdrop-filter: brightness(0.6);
}

.form-field__lock-tag {
  position: absolute;
  right: 0;
  bottom: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: calc(100% - 12px);
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 8px 0 0 0;
  font-size: 0.7rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.form-field__main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.form-field__info {
  flex: 0 1 max-content;
  min-width: 0;
  display: grid;
  gap: 2px;
}

.form-field__header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.form-field__label {
  font-weight: 600;
  font-size: 0.85rem;
}

.form-field__description {
  margin: 0;
  font-size: 0.75rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  line-height: 1.4;
}

.form-field__value-wrap {
  position: relative;
  flex: 1;
  min-width: 40px;
  max-width: 180px;
}

.form-field__tooltip {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 30;
  max-width: 280px;
  padding: 6px 8px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font-size: 0.75rem;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.15);
  pointer-events: none;
}

.form-field__value {
  width: 100%;
  flex: 1;
  min-width: 40px;
  max-width: 180px;
  min-height: 32px;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font-size: 0.8rem;
  text-align: right;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition:
    background-color 300ms ease,
    color 300ms ease,
    border-color 300ms ease;
}


.form-field__value:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>