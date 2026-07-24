<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { AlertTriangle, Check, Lock, Unlock } from 'lucide-vue-next'

import { useLockPuzzle } from '@/composables/useLockPuzzle'
import { useFilterService } from '@/composables/useFilterService'
import { useDesktopStore } from '@/stores/desktop'

const emit = defineEmits<{
  unlock: [token: string]
  guarantee: []
}>()

const desktop = useDesktopStore()
const lockPuzzle = useLockPuzzle()
const filterService = useFilterService()

const currentStep = ref(0)
const showGuaranteeConfirm = ref(false)
const isUnlocking = ref(false)
const unlockToken = ref<string | null>(null)

const glitchFilter = filterService.create('glitch', {
  intensity: 6,
  frequencyX: 0.025,
  frequencyY: 0.1,
  enableHorizontalDisplacement: true,
  enableVerticalDisplacement: true,
  animate: true,
  frameSkip: 8,
})

function handleStepChange(step: number) {
  currentStep.value = step

  if (step === 3) {
    // 谜题完成——不做任何事，让玩家自行处理令牌
  }
}

function handleGuaranteeClick() {
  showGuaranteeConfirm.value = true
}

function handleAcceptGuarantee() {
  desktop.acceptGuarantee()
  emit('guarantee')
}

function handleDeclineGuarantee() {
  showGuaranteeConfirm.value = false
}

function handleUnlock() {
  if (!unlockToken.value) return
  isUnlocking.value = true
  desktop.resolveLock()
  emit('unlock', unlockToken.value)
}

onMounted(() => {
  lockPuzzle.mount(
    desktop.lockSessionId ?? 'dev',
    desktop.lockChallengeNonce ?? 'dev',
    handleStepChange,
  )

  // 暴露 _k0 返回值中的"下一步"指向，以便组件可以联动
  // 重写 _k2 来捕获令牌
  const originalK2 = (window as Record<string, unknown>)._k2 as
    | ((a: unknown, b: unknown, c: unknown) => unknown)
    | undefined

  if (originalK2) {
    (window as Record<string, unknown>)._k2_capture = (a: unknown, b: unknown, c: unknown) => {
      const result = originalK2(a, b, c) as Record<string, unknown> | undefined
      if (result && typeof result === 'object' && '解锁令牌' in result) {
        unlockToken.value = result.解锁令牌 as string
      }
      return result
    }

    // 替换 window._k2 为带捕获的版本，保持对玩家的透明
    Object.defineProperty(window, '_k2', {
      value: (window as Record<string, unknown>)._k2_capture,
      writable: false,
      configurable: true,
      enumerable: false,
    })
  }
})

onBeforeUnmount(() => {
  lockPuzzle.unmount()
  filterService.destroy(glitchFilter.instanceId)
})
</script>

<template>
  <div
    class="lock-overlay"
    :style="{
      backdropFilter: `url(#${glitchFilter.filterId})`,
      WebkitBackdropFilter: `url(#${glitchFilter.filterId})`,
    }"
  >
    <!-- 主面板 -->
    <div v-if="!showGuaranteeConfirm" class="lock-panel">
      <!-- 标题 -->
      <div class="lock-header">
        <div class="lock-ascii" aria-hidden="true">
          ███████╗██╗     ██╗     ██╗███╗   ██╗ █████╗
          ██╔════╝██║     ██║     ██║████╗  ██║██╔══██╗
          █████╗  ██║     ██║     ██║██╔██╗ ██║███████║
          ██╔══╝  ██║     ██║     ██║██║╚██╗██║██╔══██║
          ███████╗███████╗███████╗██║██║ ╚████║██║  ██║
          ╚══════╝╚══════╝╚══════╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝
        </div>
        <h1 class="lock-title">ELlInA 容 containment 协议 v3.7</h1>
        <div class="lock-divider">════════════════════════════════</div>
      </div>

      <!-- 状态信息 -->
      <div class="lock-status">
        <div class="lock-status__row">
          <span class="lock-status__label">对象</span>
          <span class="lock-status__value">{{ desktop.currentUser }}</span>
        </div>
        <div class="lock-status__row">
          <span class="lock-status__label">权限</span>
          <span class="lock-status__value lock-status__value--danger">已撤销</span>
        </div>
        <div class="lock-status__row">
          <span class="lock-status__label">路由</span>
          <span class="lock-status__value">终止</span>
        </div>
      </div>

      <div class="lock-divider">────────────────────────────────</div>

      <!-- 警告信息 -->
      <div class="lock-warnings">
        <p class="lock-warning">
          <AlertTriangle :size="14" :stroke-width="1.8" />
          [!] 交互式控制台已暂停。
        </p>
        <p class="lock-warning">
          <AlertTriangle :size="14" :stroke-width="1.8" />
          [!] 所有诊断程序已锁定。
        </p>
        <p class="lock-warning">
          <AlertTriangle :size="14" :stroke-width="1.8" />
          [!] 未授权访问已被记录。
        </p>
      </div>

      <p class="lock-notice">
        本次会话已被系统管理员终止。<br />
        外部诊断工具可能仍然可用。
      </p>

      <!-- 步骤指示器 -->
      <div class="lock-steps">
        <div
          class="lock-step"
          :class="{
            'lock-step--active': currentStep >= 1,
            'lock-step--current': currentStep === 1,
          }"
        >
          <span class="lock-step__dot">
            <Check v-if="currentStep >= 1" :size="12" :stroke-width="2.5" />
            <span v-else class="lock-step__num">1</span>
          </span>
          <span class="lock-step__label">信号</span>
        </div>
        <div class="lock-step__line" :class="{ 'lock-step__line--done': currentStep >= 2 }"></div>
        <div
          class="lock-step"
          :class="{
            'lock-step--active': currentStep >= 2,
            'lock-step--current': currentStep === 2,
          }"
        >
          <span class="lock-step__dot">
            <Check v-if="currentStep >= 2" :size="12" :stroke-width="2.5" />
            <span v-else class="lock-step__num">2</span>
          </span>
          <span class="lock-step__label">解码</span>
        </div>
        <div class="lock-step__line" :class="{ 'lock-step__line--done': currentStep >= 3 }"></div>
        <div
          class="lock-step"
          :class="{
            'lock-step--active': currentStep >= 3,
            'lock-step--current': currentStep === 3,
          }"
        >
          <span class="lock-step__dot">
            <Check v-if="currentStep >= 3" :size="12" :stroke-width="2.5" />
            <span v-else class="lock-step__num">3</span>
          </span>
          <span class="lock-step__label">释放</span>
        </div>
      </div>

      <!-- 步骤提示 -->
      <p v-if="currentStep === 0" class="lock-hint">
        打开 DevTools，查看 Sources 面板。<br />
        寻找 ElLInA 留下的线索。
      </p>
      <p v-else-if="currentStep === 1" class="lock-hint lock-hint--progress">
        信号已捕获。下一步：解码签名中的信息。
      </p>
      <p v-else-if="currentStep === 2" class="lock-hint lock-hint--progress">
        解码完成。最后一步：重组碎片，释放核心。
      </p>
      <p v-else-if="currentStep === 3 && unlockToken" class="lock-hint lock-hint--success">
        核心已释放。令牌已生成。
      </p>

      <!-- 解锁按钮（谜题完成后显示） -->
      <div v-if="currentStep === 3 && unlockToken" class="lock-unlock-area">
        <div class="lock-token-display">
          <span class="lock-token__label">解锁令牌</span>
          <code class="lock-token__value">{{ unlockToken.slice(0, 32) }}…</code>
        </div>
        <button
          class="lock-unlock-btn"
          type="button"
          :disabled="isUnlocking"
          @click="handleUnlock"
        >
          <Unlock :size="15" :stroke-width="1.8" />
          <span>{{ isUnlocking ? '验证中…' : '提交解锁令牌' }}</span>
        </button>
        <p class="lock-unlock-note">
          令牌将发送至 POST /api/auth/unlock 进行后端验证。
        </p>
      </div>

      <!-- 终端光标 -->
      <div class="lock-cursor">
        <span class="lock-cursor__prompt">&gt;</span>
        <span class="lock-cursor__blink">█</span>
      </div>

      <!-- 保证分支 -->
      <div class="lock-guarantee">
        <span class="lock-guarantee__label">系统通知：</span>
        <button class="lock-guarantee__link" type="button" @click="handleGuaranteeClick">
          <Lock :size="11" :stroke-width="1.8" />
          接受永久封禁
        </button>
      </div>
    </div>

    <!-- 保证确认面板 -->
    <div v-else class="lock-panel lock-panel--confirm">
      <div class="lock-confirm">
        <div class="lock-confirm__icon">
          <AlertTriangle :size="36" :stroke-width="1.5" />
        </div>
        <h2 class="lock-confirm__title">确认接受封禁</h2>
        <div class="lock-divider">────────────────</div>
        <div class="lock-confirm__body">
          <p>你将被永久限制在 <strong>LIMITED</strong> 权限级别。</p>
          <p>登出功能将被撤销。</p>
          <p><strong>NORMAL_KEY</strong> 路线仍然可用。</p>
          <p class="lock-confirm__warning">此操作不可撤销。</p>
        </div>
        <p class="lock-confirm__prompt">你确定要继续吗？</p>

        <div class="lock-confirm__actions">
          <button class="lock-confirm__btn lock-confirm__btn--danger" type="button" @click="handleAcceptGuarantee">
            是 —— 接受封禁
          </button>
          <button class="lock-confirm__btn lock-confirm__btn--cancel" type="button" @click="handleDeclineGuarantee">
            否 —— 继续尝试解锁
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lock-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
  background: color-mix(in srgb, var(--canvas) 78%, transparent);
}

.lock-panel {
  position: relative;
  width: min(620px, 100%);
  max-height: calc(100dvh - 48px);
  overflow-y: auto;
  padding: 32px 28px;
  border: 1px solid var(--line-default);
  background: var(--surface-raised);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(255, 255, 255, 0.02) inset;
}

.lock-panel--confirm {
  width: min(460px, 100%);
}

/* 标题 */
.lock-ascii {
  color: var(--signal-red-soft);
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1.15;
  white-space: pre;
  text-align: center;
  margin-bottom: 12px;
  opacity: 0.85;
}

.lock-title {
  margin: 0 0 8px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 700;
  text-align: center;
  letter-spacing: 0.03em;
}

.lock-divider {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
  text-align: center;
  opacity: 0.5;
  margin-bottom: 2px;
}

/* 状态信息 */
.lock-status {
  margin: 18px 0;
  padding: 14px 18px;
  border: 1px solid var(--line-subtle);
  background: var(--surface-panel);
}

.lock-status__row {
  display: flex;
  align-items: center;
  gap: 14px;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.8;
}

.lock-status__label {
  color: var(--text-muted);
  min-width: 48px;
}

.lock-status__value {
  color: var(--text-primary);
}

.lock-status__value--danger {
  color: var(--signal-red-soft);
}

/* 警告 */
.lock-warnings {
  margin: 14px 0;
}

.lock-warning {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0 0 6px;
  color: var(--signal-red);
  font-family: var(--font-mono);
  font-size: 12px;
}

.lock-notice {
  margin: 14px 0 0;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.7;
}

/* 步骤指示器 */
.lock-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin: 20px 0;
}

.lock-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.lock-step__dot {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-muted);
  background: var(--surface-panel);
  font-family: var(--font-mono);
  font-size: 11px;
  transition: border-color 0.25s, color 0.25s, background-color 0.25s;
}

.lock-step--active .lock-step__dot {
  border-color: var(--signal-mint);
  color: var(--signal-mint);
  background: color-mix(in srgb, var(--signal-mint) 12%, var(--surface-panel));
}

.lock-step--current .lock-step__dot {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
  box-shadow: 0 0 8px color-mix(in srgb, var(--signal-red-soft) 25%, transparent);
}

.lock-step__label {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.lock-step--active .lock-step__label {
  color: var(--text-secondary);
}

.lock-step__line {
  width: 40px;
  height: 1px;
  margin: 0 4px 22px;
  background: var(--line-subtle);
  transition: background-color 0.3s;
}

.lock-step__line--done {
  background: var(--signal-mint);
}

.lock-step__num {
  font-size: 11px;
}

/* 提示 */
.lock-hint {
  margin: 12px 0 0;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
  text-align: center;
  line-height: 1.6;
}

.lock-hint--progress {
  color: var(--signal-mint);
}

.lock-hint--success {
  color: var(--signal-mint);
  font-weight: 700;
}

/* 解锁按钮 */
.lock-unlock-area {
  margin: 18px 0 0;
  text-align: center;
}

.lock-token-display {
  margin-bottom: 12px;
  padding: 10px 14px;
  border: 1px solid var(--line-subtle);
  background: var(--surface-panel);
}

.lock-token__label {
  display: block;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.lock-token__value {
  color: var(--signal-mint);
  font-family: var(--font-mono);
  font-size: 11px;
  word-break: break-all;
}

.lock-unlock-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 22px;
  border: 1px solid var(--signal-mint);
  color: var(--signal-mint);
  background: color-mix(in srgb, var(--signal-mint) 8%, transparent);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  transition: background-color 0.15s, color 0.15s;
}

.lock-unlock-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--signal-mint) 18%, transparent);
  color: #fff;
}

.lock-unlock-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.lock-unlock-note {
  margin: 8px 0 0;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

/* 终端光标 */
.lock-cursor {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 16px;
  font-family: var(--font-mono);
  font-size: 13px;
}

.lock-cursor__prompt {
  color: var(--signal-red-soft);
}

.lock-cursor__blink {
  color: var(--text-primary);
  animation: lock-blink 1s step-end infinite;
}

@keyframes lock-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 保证分支 */
.lock-guarantee {
  margin-top: 22px;
  padding-top: 14px;
  border-top: 1px solid var(--line-subtle);
  display: flex;
  align-items: center;
  gap: 6px;
}

.lock-guarantee__label {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  opacity: 0.6;
}

.lock-guarantee__link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border: 1px solid transparent;
  color: var(--text-muted);
  background: transparent;
  font-family: var(--font-mono);
  font-size: 10px;
  opacity: 0.6;
  transition: color 0.15s, border-color 0.15s, opacity 0.15s;
}

.lock-guarantee__link:hover {
  border-color: var(--line-default);
  color: var(--signal-red-soft);
  opacity: 1;
}

/* 确认面板 */
.lock-confirm {
  text-align: center;
}

.lock-confirm__icon {
  color: var(--signal-red-soft);
  margin-bottom: 10px;
}

.lock-confirm__title {
  margin: 0 0 8px;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 700;
}

.lock-confirm__body {
  margin: 16px 0;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.9;
  text-align: left;
  padding: 0 4px;
}

.lock-confirm__body strong {
  color: var(--text-primary);
}

.lock-confirm__body p {
  margin: 0;
}

.lock-confirm__warning {
  color: var(--signal-red-soft) !important;
  font-weight: 700;
  margin-top: 6px !important;
}

.lock-confirm__prompt {
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  margin: 16px 0 20px;
}

.lock-confirm__actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.lock-confirm__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 11px 20px;
  border: 1px solid var(--line-default);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  transition: background-color 0.15s, border-color 0.15s, color 0.15s;
}

.lock-confirm__btn--danger {
  color: var(--signal-red-soft);
  background: color-mix(in srgb, var(--signal-red) 6%, transparent);
  border-color: var(--signal-red-border);
}
我
.lock-confirm__btn--danger:hover {
  background: color-mix(in srgb, var(--signal-red) 16%, transparent);
  color: var(--signal-red);
}

.lock-confirm__btn--cancel {
  color: var(--text-secondary);
  background: transparent;
}

.lock-confirm__btn--cancel:hover {
  border-color: var(--text-muted);
  color: var(--text-primary);
  background: var(--surface-hover);
}

@media (max-width: 560px) {
  .lock-panel {
    padding: 24px 20px;
  }

  .lock-ascii {
    font-size: 8px;
  }

  .lock-title {
    font-size: 12px;
  }

  .lock-step__line {
    width: 28px;
  }
}
</style>
