<script setup lang="ts">
/**
 * # Browser.vue — 浏览器应用
 *
 * 窗口结构：窗口框架（WindowFrame）→ 网址栏 → 网页内容（iframe）。
 *
 * ## 功能
 *
 * - 地址栏输入网址，回车或点"前往"加载
 * - **安全拦截（仅受限账号生效）**：危险协议（file:/data:/javascript: 等）、
 *   localhost、私有/内网 IP 网段（含 127.1、0x7f000001、[::1] 等变形形式）
 *   对 LIMITED 账号一律不予放行，内容区显示"禁止访问"占位页（FakeOS 风格）；
 *   管理员（JDK 触发器，ADMIN）不受此限制
 * - 无协议输入自动补 `https://`
 *
 * ## 为什么拦截这些地址
 *
 * 玩家浏览器若加载 localhost / 127.0.0.1 即可访问本机服务（如后端 API、
 * 开发者工具），这与"沙盒内玩家权限受限"的叙事冲突，也属于潜在越权面。
 * 判定逻辑集中在 useBrowserPolicy.ts（协议 → 主机名 → IP 网段三层），
 * 是否启用拦截由当前账号权限（desktopStore.privilegeClass）决定，
 * 与文件系统 / 终端共用同一套权限来源。
 *
 * ## 与 darksky 分支区别
 *
 * darksky 分支无此应用。本组件依赖本分支的注册表应用 + Dock 条目机制。
 */

import { onBeforeUnmount, ref, watch } from 'vue'
import { ShieldX } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { useFilterService } from '@/composables/useFilterService'
import { evaluateBrowserAddress } from '@/composables/useBrowserPolicy'
import { useDesktopStore } from '@/stores/desktop'

const { t } = useI18n({ useScope: 'global' })
const filterService = useFilterService()
const desktop = useDesktopStore()

/** 地址栏输入值 */
const address = ref('https://example.com')
/** 当前 iframe 加载地址（denied 时为 ''） */
const currentSrc = ref('https://example.com')
/** 是否命中禁止访问（localhost / 127.0.0.1） */
const denied = ref(false)

// ─── 错误破碎感（glitch 滤镜） ──────────────────────

/** 禁止访问时创建的 glitch 滤镜实例（denied 才创建，避免常驻消耗） */
let glitchHandle: { instanceId: string; filterId: string } | null = null
/** 当前生效的 glitch 滤镜 id（模板绑定用 ref，避免 vue-tsc 对闭包 let 的推断问题） */
const glitchFilterId = ref<string | null>(null)

// denied 为 true 时创建故障滤镜，恢复或卸载时销毁。
// 复用 App 级 FilterService（App.vue 渲染 FilterHost 挂载 SVG 滤镜定义），
// 面板通过 url(#filterId) 引用，产生与 LockPage 一致的色差+位移故障效果。
watch(
  denied,
  (isDenied) => {
    if (isDenied && !glitchHandle) {
      glitchHandle = filterService.create('glitch', {
        intensity: 20,
        frequencyX: 0.03,
        frequencyY: 0.12,
        enableHorizontalDisplacement: true,
        enableVerticalDisplacement: true,
        chromaticAberration: 0.0015,
        animate: true,
        frameSkip: 10,
      })
      glitchFilterId.value = glitchHandle.filterId
    } else if (!isDenied && glitchHandle) {
      filterService.destroy(glitchHandle.instanceId)
      glitchHandle = null
      glitchFilterId.value = null
    }
  },
  { immediate: true },
)

// ─── 禁止访问演出（仿 StoryDialog 打字机） ───────────

/** 已打出的标题文字（逐字追加） */
const deniedTitle = ref('')
/** 打字完成后是否显示闪烁光标 */
const showDeniedCursor = ref(false)
/** 打字定时器 */
let deniedTimer: ReturnType<typeof setInterval> | null = null

/**
 * 触发禁止访问演出：标题逐字打出，结束显示闪烁光标。
 * 复用 StoryDialog 的打字机节奏（interval + slice），让"禁止访问"
 * 从静态大字变成一段简短演出。
 *
 * @param title - 要逐字打出的标题文本（i18n 翻译后的字符串）
 */
function playDeniedShow(title: string) {
  deniedTitle.value = ''
  showDeniedCursor.value = false
  if (deniedTimer !== null) clearInterval(deniedTimer)
  let cursor = 0
  deniedTimer = setInterval(() => {
    cursor += 1
    deniedTitle.value = title.slice(0, cursor)
    if (cursor >= title.length) {
      if (deniedTimer !== null) clearInterval(deniedTimer)
      deniedTimer = null
      showDeniedCursor.value = true
    }
  }, 120)
}

onBeforeUnmount(() => {
  if (deniedTimer !== null) clearInterval(deniedTimer)
  if (glitchHandle) filterService.destroy(glitchHandle.instanceId)
})

/**
 * 规范化地址：带协议的保留，无协议补 https://。
 *
 * @param raw - 地址栏原始输入
 * @returns 可用于 iframe src 的 URL
 */
function normalizeUrl(raw: string): string {
  const trimmed = raw.trim()
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

/** 前往按钮 / 回车：安全校验并加载目标地址 */
function navigate() {
  const raw = address.value
  if (!raw.trim()) return
  // 安全拦截仅对受限账号（LIMITED）生效；管理员（JDK 触发器，ADMIN）不受限。
  // 判定逻辑见 useBrowserPolicy.ts
  denied.value = desktop.privilegeClass === 'LIMITED' && !evaluateBrowserAddress(raw)
  if (denied.value) {
    currentSrc.value = ''
    playDeniedShow(t('browser.deniedTitle'))
    return
  }
  currentSrc.value = normalizeUrl(raw)
}
</script>

<template>
  <div class="browser">
    <!-- 网址栏 -->
    <div class="browser__toolbar">
      <input
        v-model="address"
        class="browser__address"
        type="url"
        :placeholder="t('browser.addressPlaceholder')"
        :aria-label="t('browser.addressPlaceholder')"
        spellcheck="false"
        @keyup.enter="navigate"
        @change="navigate"
      />
      <button class="browser__go" type="button" @click="navigate">
        {{ t('browser.go') }}
      </button>
    </div>

    <!-- 内容区：禁止访问占位页 或 iframe 网页 -->
    <div class="browser__content">
      <div v-if="denied" class="browser__denied">
        <div
          class="browser__denied-panel"
          :style="glitchFilterId ? { filter: `url(#${glitchFilterId})` } : undefined"
        >
          <div class="browser__denied-badge">
            <ShieldX :size="44" :stroke-width="1.2" class="browser__denied-icon" />
          </div>
          <p class="browser__denied-title">
            {{ deniedTitle }}<span v-if="showDeniedCursor" class="browser__denied-cursor">_</span>
          </p>
        </div>
      </div>
      <iframe
        v-else
        class="browser__frame"
        :src="currentSrc"
        :title="t('applications.browser.title')"
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
      ></iframe>
    </div>
  </div>
</template>

<style scoped>
.browser {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  background: var(--canvas);
}

/* ── 网址栏 ── */
.browser__toolbar {
  display: flex;
  flex-shrink: 0;
  gap: 6px;
  padding: 8px;
  border-bottom: 1px solid var(--line-subtle);
  background: var(--surface-panel);
}

.browser__address {
  flex: 1;
  min-width: 0;
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  outline: none;
  color: var(--text-primary);
  background: var(--canvas);
  font: 12px var(--font-mono);
  transition: border-color 0.12s;
}

.browser__address:focus {
  border-color: var(--signal-mint);
}

.browser__go {
  flex-shrink: 0;
  min-width: 72px;
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: transparent;
  font: 600 11px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.browser__go:hover {
  border-color: var(--signal-mint);
  color: var(--signal-mint);
  background: var(--surface-hover);
}

/* ── 内容区 ── */
.browser__content {
  flex: 1;
  min-height: 0;
  position: relative;
  background: var(--canvas);
}

.browser__frame {
  width: 100%;
  height: 100%;
  border: none;
  background: #fff;
}

/* ── 禁止访问页（仿拒绝访问弹窗样式） ── */
.browser__denied {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(32, 32, 38, 0.5);
}

/* 仿 WindowFrame 弹窗外观的面板（边框 + 阴影 + 面板底色）。
   叠加"错误破碎感"：clip-path 切出缺角 + 扫描线 + 轻微抖动，配合 glitch 滤镜。 */
.browser__denied-panel {
  position: relative;
  min-width: 320px;
  padding: 40px 48px 44px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  background: var(--surface-raised);
  box-shadow: 0 18px 56px rgba(0, 0, 0, 0.45);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
  text-align: center;
  /* 缺角：右上和左下被"咬掉"，模拟信号撕裂/破碎的边缘 */
  clip-path: polygon(
    0 0,
    calc(100% - 22px) 0,
    100% 22px,
    100% 100%,
    22px 100%,
    0 calc(100% - 22px)
  );
  animation: denied-shake 0.32s steps(2) infinite;
}

/* CRT 扫描线，叠在面板内容之上强化"故障显示器"氛围 */
.browser__denied-panel::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: repeating-linear-gradient(
    to bottom,
    rgba(255, 255, 255, 0.03) 0 1px,
    transparent 1px 3px
  );
  mix-blend-mode: overlay;
}

.browser__denied-badge {
  animation: denied-pop-in 0.45s ease-out both;
}

.browser__denied-icon {
  color: var(--signal-red-soft);
}

.browser__denied-title {
  min-height: 1em;
  margin: 0;
  color: var(--signal-red);
  font: 700 32px var(--font-mono);
  letter-spacing: 0.08em;
  /* 静态色差：红/青错边，模拟 RGB 通道未对齐 */
  text-shadow:
    2px 0 rgba(255, 0, 60, 0.55),
    -2px 0 rgba(0, 229, 255, 0.45);
}

.browser__denied-cursor {
  animation: cursor-blink 0.8s steps(1) infinite;
}

/* 盾牌图标弹入（缩小+淡入） */
@keyframes denied-pop-in {
  from {
    opacity: 0;
    transform: scale(0.6);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* 面板细微抖动：像素级位移，故障"不稳"感 */
@keyframes denied-shake {
  0%,
  100% {
    transform: translate(0, 0);
  }
  20% {
    transform: translate(-1px, 0);
  }
  40% {
    transform: translate(1px, 1px);
  }
  60% {
    transform: translate(0, -1px);
  }
  80% {
    transform: translate(-1px, 1px);
  }
}

/* 打字完成后的闪烁光标（与 StoryDialog 一致的节拍） */
@keyframes cursor-blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}
</style>
