<script setup lang="ts">
/**
 * # 鉴权网关页面
 *
 * 访问 `/console/` 时的第一道关卡。
 * 检查 localStorage 中是否有有效 token：
 * - 已认证 → 直接进入桌面
 * - 未认证 → 显示倒计时提示，3 秒后自动跳转登录页
 *
 * ## 背景效果
 *
 * 使用 Canvas 渲染 0/1 ASCII 码雨背景，亮度约 50%，
 * 实现若隐若现的科技感背景。
 *
 * ## 设计决策
 *
 * 不使用 route guard 直接重定向到 /login，而是先渲染一个中间页面，
 * 给用户明确的"鉴权失败"反馈，避免用户困惑"为什么直接跳到登录页"。
 */

import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ShieldAlert } from 'lucide-vue-next'
import { useAuth } from '@/composables/useAuth'

const { t } = useI18n({ useScope: 'global' })
const router = useRouter()
const auth = useAuth()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const countdown = ref(3)
let timer: ReturnType<typeof setInterval> | null = null

/** ASCII 码雨背景 */
let animationId: number | null = null
let drops: number[] = []
let columns = 0
let ctx: CanvasRenderingContext2D | null = null

const FONT_SIZE = 14
const CHARS = '0101010101  '

function initAsciiRain(canvas: HTMLCanvasElement) {
  const dpr = window.devicePixelRatio || 1
  ctx = canvas.getContext('2d')!

  function resize() {
    const w = window.innerWidth
    const h = window.innerHeight
    canvas.width = w * dpr
    canvas.height = h * dpr
    canvas.style.width = `${w}px`
    canvas.style.height = `${h}px`
    ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)

    columns = Math.floor(w / FONT_SIZE)
    drops = Array.from({ length: columns }, () => Math.floor(Math.random() * -20))
  }

  resize()
  window.addEventListener('resize', resize)

  function draw() {
    if (!ctx) return
    const w = window.innerWidth
    const h = window.innerHeight

    // 半透明黑色拖尾，制造渐隐效果
    ctx.fillStyle = 'rgba(13, 13, 15, 0.08)'
    ctx.fillRect(0, 0, w, h)

    ctx.font = `600 ${FONT_SIZE}px "Courier New", monospace`
    ctx.textBaseline = 'top'

    for (let i = 0; i < drops.length; i++) {
      const char = CHARS[Math.floor(Math.random() * CHARS.length)]
      const x = i * FONT_SIZE
      const y = drops[i] * FONT_SIZE

      // 亮度约 50% 的灰绿色
      if (Math.random() > 0.7) {
        ctx.fillStyle = 'rgba(180, 200, 190, 0.25)'
      } else {
        ctx.fillStyle = 'rgba(150, 170, 160, 0.15)'
      }

      ctx.fillText(char, x, y)

      if (y > h && Math.random() > 0.975) {
        drops[i] = 0
      }
      drops[i]++
    }

    animationId = requestAnimationFrame(draw)
  }

  draw()

  return () => {
    window.removeEventListener('resize', resize)
    if (animationId !== null) {
      cancelAnimationFrame(animationId)
      animationId = null
    }
    ctx = null
  }
}

let cleanupRain: (() => void) | null = null

function goToLogin() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  router.replace({ name: 'login' })
}

onMounted(() => {
  // 已认证 → 直接进入桌面
  if (auth.isAuthenticated.value) {
    router.replace({ name: 'desktop' })
    return
  }

  // 启动 ASCII 码雨背景
  if (canvasRef.value) {
    cleanupRain = initAsciiRain(canvasRef.value)
  }

  // 未认证 → 倒计时跳转
  timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      goToLogin()
    }
  }, 1000)
})

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  cleanupRain?.()
})
</script>

<template>
  <div class="auth-gate">
    <canvas ref="canvasRef" class="auth-gate__bg" />
    <div class="auth-gate__card">
      <ShieldAlert :size="36" :stroke-width="1.5" class="auth-gate__icon" />
      <h1 class="auth-gate__title">{{ t('authGate.failed') }}</h1>
      <p class="auth-gate__subtitle">
        {{ t('authGate.redirecting', { seconds: countdown }) }}
      </p>
      <button class="auth-gate__skip" type="button" @click="goToLogin">
        {{ t('authGate.skipButton') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.auth-gate {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100dvh;
  background: var(--canvas);
  overflow: hidden;
}

.auth-gate__bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.auth-gate__card {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px 48px;
  border: 1px solid var(--line-default);
  background: var(--surface-raised);
  text-align: center;
  max-width: 360px;
}

.auth-gate__icon {
  color: var(--signal-red);
  margin-bottom: 4px;
}

.auth-gate__title {
  margin: 0;
  color: var(--text-primary);
  font: 700 18px var(--font-ui);
}

.auth-gate__subtitle {
  margin: 0;
  color: var(--text-secondary);
  font: 13px var(--font-ui);
  line-height: 1.5;
}

.auth-gate__skip {
  margin-top: 8px;
  padding: 8px 24px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-secondary);
  background: transparent;
  font: 600 12px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.auth-gate__skip:hover {
  border-color: var(--signal-mint);
  color: var(--signal-mint);
  background: var(--surface-hover);
}
</style>
