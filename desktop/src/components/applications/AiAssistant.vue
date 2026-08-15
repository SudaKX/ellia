<script setup lang="ts">
/**
 * # AiAssistant.vue — AI 助手窗口（贴边对话 / 彩蛋浮窗双态）
 *
 * 内嵌在 WindowFrame 中运行的 AI 助手面板，由 DesktopView 在 onMounted 时
 * 通过 windowService.send 创建（layer: 'ai'，常驻于普通窗口之上、模态之下）。
 *
 * ## 双状态机
 *
 * - **离开态（detached，默认）**：现有彩蛋浮窗行为——
 *   点击人物图轮换 kei 表情/台词/语音；拖动结束若靠近某普通窗口边缘 → 贴合。
 * - **贴合态（attached）**：贴到目标窗口边上（一起移动），切换为对话模式——
 *   表情差分 + 打字机文字 + ≤4 个选项；监听目标窗口联动事件（如谜题输错）。
 *
 * ## 状态切换
 *
 * - 贴合：拖动到目标窗口边缘（距离 < 24px）自动吸附 / 点击"贴合"键绑定上一个焦点窗口
 * - 分离：快速摇动 / 点击"分离"键 / 目标窗口关闭 / 点击关闭键（贴合时）
 *
 * ## 与目标窗口的联动
 *
 * - 目标窗口 → AI：useAiLiaison.notifyAi（如谜题输错 N 次）
 * - AI → 目标窗口：useAiLiaison.sendHostAction（开提示、填答案等）
 *   （"开提示"先扣 TVB 积分，余额不足则不发操作并切换台词）
 *
 * ## 关闭键语义
 *
 * 贴合时点击关闭键 = 分离（由 DesktopView 经 requestAiDetach 转发）；
 * 离开态点击关闭键 = 现有随机漂移行为（DesktopView.handleAiCloseRequest）。
 */

import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { expressionImage } from '@/ai/expressions'
import { resolveScript } from '@/ai/scripts'
import type { AiChoice, AiExpression, AiNode } from '@/ai/types'
import { onAiEvent, registerAiAttach, registerAiDetach, registerAiDragHandlers, sendHostAction, setAiLiaisonState } from '@/ai/useAiLiaison'
import { useAudioService } from '@/composables/useAudioService'
import { useHalftone } from '@/composables/useHalftone'
import { WINDOW_FRAME_ID } from '@/composables/windowFrameId'
import type { WindowService } from '@/composables/useWindowService'
import { useCreditsStore } from '@/stores/credits'
import type { WindowInstance } from '@/types/desktop'

const props = defineProps<{
  /** kei 表情图片 URL 数组，点击轮换（离开态） */
  images: string[]
  /** 标题栏台词数组，与图片同步轮换 */
  titles: string[]
  /** kei 语音文件 URL 数组，点击时按顺序循环播放 */
  voices: string[]
  /** 更新标题栏文本的回调 */
  onSetTitle?: (text: string) => void
  /** 外部强制覆盖图片 URL（右键"问AI"等场景）。null 时正常轮换 */
  overrideImage?: string | null
}>()

const { t } = useI18n({ useScope: 'global' })
const audioService = useAudioService()
const halftone = useHalftone({ dotSpacing: 3, maxRadius: 2.5, minRadius: 0.6 })
const windowService = inject<WindowService | null>('windowService', null)
const selfWindowId = inject<string | null>(WINDOW_FRAME_ID, null)
const creditsStore = useCreditsStore()

// ─── 常量 ──────────────────────────────────────────────

/** 贴合态对话窗口宽度 */
const AI_CHAT_WIDTH = 240
/** 贴合态对话窗口高度（固定，不随主窗口缩放变化） */
const AI_CHAT_HEIGHT = 320
/** 贴合时与目标窗口的边距 */
const EDGE_GAP = 12
/** 自动贴合判定的最近边距阈值（px） */
const ATTACH_THRESHOLD = 24
/** 摇动分离：方向反转次数阈值 */
const SHAKE_THRESHOLD = 6
/** 摇动采样点数 */
const SHAKE_SAMPLES = 12
/** 摇动采样时间窗（ms） */
const SHAKE_WINDOW_MS = 800
/** 打字机每字符间隔（ms） */
const TYPING_DELAY_MS = 30
/** 贴合态手动拉开分离的距离阈值（px） */
const DETACH_DRAG_DISTANCE = 80
/** AI 帮开提示的 TVB 扣费 */
const AI_HINT_COST = 30
/** 选项数量上限 */
const MAX_AI_CHOICES = 4

// ─── 离开态状态（彩蛋浮窗） ─────────────────────────────

const currentIndex = ref(0)
const currentImage = computed(() => props.overrideImage ?? (props.images[currentIndex.value] || props.images[0]))
const canvasRef = ref<HTMLCanvasElement | null>(null)

// ─── 贴合态状态（对话模式） ─────────────────────────────

const liaisonState = ref<'detached' | 'attached'>('detached')
const hostWindowId = ref<string | null>(null)
/** 上一个非 AI 焦点窗口（"贴合"键绑定目标） */
let lastHostCandidate: string | null = null
/** 当前播放的剧本节点 */
const script = ref<AiNode[]>([])
const nodeIndex = ref(0)
const typedText = ref('')
const isTyping = ref(false)
const currentExpression = ref<AiExpression>('normal')
const hostTitle = ref('')

let typeTimer: ReturnType<typeof setInterval> | null = null
let followRaf = 0
/** 摇动采样缓冲：{x, y, t} */
const shakeSamples: { x: number; y: number; t: number }[] = []
/** 是否正在拖拽（贴合态拖动时暂停跟随，避免与玩家拖动对抗） */
let isAiDragging = false
/** 本次拖动以摇动分离结束 → 松手时跳过贴合检测（避免立即重新贴合） */
let suppressAttachOnce = false

const isAttached = computed(() => liaisonState.value === 'attached')
const current = computed(() => script.value[nodeIndex.value] ?? null)
const displayImage = computed(() =>
  isAttached.value ? expressionImage(currentExpression.value) : currentImage.value,
)
/**
 * "大头照"待机态：贴合中且没有聊天文字（剧本结束 / 无对白节点）时，
 * 表情大图占满整个内容区（隐藏文字区与选项行）。
 */
const isPortraitMode = computed(() =>
  isAttached.value && !typedText.value && !current.value?.choices,
)

// ─── 窗口实例辅助 ──────────────────────────────────────

function findWindow(id: string): WindowInstance | null {
  return windowService?.windows.value.find((w) => w.id === id) ?? null
}

/** 更新自身窗口实例（shallowRef 数组需 splice 替换以触发响应式） */
function updateSelfWindow(partial: Partial<WindowInstance>): void {
  const list = windowService?.windows.value
  if (!list || !selfWindowId) return
  const idx = list.findIndex((w) => w.id === selfWindowId)
  if (idx === -1) return
  list.splice(idx, 1, { ...list[idx], ...partial })
}

// ─── halftone 渲染（现有） ──────────────────────────────

onMounted(async () => {
  if (canvasRef.value) {
    await halftone.init(canvasRef.value)
    await halftone.render(displayImage.value)
  }

  // 注册与 DesktopView 的通信回调（标题栏贴合/分离按钮 + 拖拽检测）
  registerAiDetach(() => detach())
  registerAiAttach(() => handleAttachBtn())
  registerAiDragHandlers({ onDragMove: handleAiDragMove, onDragEnd: handleAiDragEnd })

  // 订阅目标窗口联动事件
  aiEventOff = onAiEvent(handleAiEvent)
})

onBeforeUnmount(() => {
  halftone.destroy()
  stopTyping()
  stopFollowLoop()
  aiEventOff?.()
})

watch(displayImage, (url) => {
  halftone.render(url)
})

// 切换贴合/离开时窗口尺寸变化，等布局稳定后重绘点阵
watch(liaisonState, () => {
  nextTick(() => halftone.render(displayImage.value))
})

// 缓存"上一个非 AI 焦点窗口"，供"贴合"键绑定
watch(
  () => windowService?.activeWindowId.value,
  (id) => {
    if (id && id !== selfWindowId) lastHostCandidate = id
  },
)

// ─── 离开态交互（现有轮换） ─────────────────────────────

function handleImageClick() {
  // 贴合态不轮换——表情由剧本差分控制
  if (isAttached.value) return
  currentIndex.value = (currentIndex.value + 1) % props.images.length
  // 语音和台词共用同一个映射索引（0/1/2 对应 ogg1/2/3 和台词1/2/3）
  const mapIndex = currentIndex.value % Math.min(props.titles.length, props.voices.length || 1)
  if (props.titles.length > 0) {
    props.onSetTitle?.(props.titles[mapIndex])
  }
  if (props.voices.length > 0) {
    audioService.playFile(props.voices[mapIndex])
  }
}

// ─── 贴合 / 分离 ───────────────────────────────────────

function attachTo(windowId: string): void {
  if (isAttached.value) return
  const host = findWindow(windowId)
  if (!host) return

  hostWindowId.value = windowId
  liaisonState.value = 'attached'
  setAiLiaisonState('attached')
  hostTitle.value = host.title ?? t(host.titleKey)
  props.onSetTitle?.(t('aiChat.attachedTitle', { title: hostTitle.value }))

  playScript(resolveScript(host))
  applyAttachedBounds()
  startFollowLoop()
}

/**
 * 分离到离开态。返回 true 表示确实处于贴合态并已分离（供关闭键判断）。
 */
function detach(): boolean {
  if (!isAttached.value) return false

  stopTyping()
  stopFollowLoop()
  hostWindowId.value = null
  liaisonState.value = 'detached'
  setAiLiaisonState('detached')
  script.value = []
  nodeIndex.value = 0
  typedText.value = ''
  isTyping.value = false
  currentExpression.value = 'normal'
  hostTitle.value = ''
  shakeSamples.length = 0

  // 恢复离开态几何（默认尺寸 + 右下角），恢复可缩放
  const width = 552
  const height = 586
  const padding = 16
  updateSelfWindow({
    width,
    height,
    x: Math.max(0, window.innerWidth - width - padding),
    y: Math.max(0, window.innerHeight - height - 90),
    resizable: true,
    isMinimized: false,
  })
  props.onSetTitle?.(props.titles[0] ?? '')
  return true
}

/**
 * "贴合"键：绑定上一个焦点窗口（缺省回退当前活动窗口）。
 * 返回是否已贴合（供标题栏按钮判断）。
 */
function handleAttachBtn(): boolean {
  if (isAttached.value) return true
  const active = windowService?.activeWindowId.value
  const target = lastHostCandidate ?? (active !== selfWindowId ? active : null)
  if (target) {
    attachTo(target)
    return isAttached.value
  }
  return false
}

// ─── 贴合检测（拖动结束） ───────────────────────────────

function handleAiDragEnd(): void {
  isAiDragging = false
  shakeSamples.length = 0

  // 本次拖动以摇动分离结束：松手时跳过贴合检测，避免立即重新贴合
  if (suppressAttachOnce) {
    suppressAttachOnce = false
    return
  }

  if (isAttached.value) {
    // 已贴合：玩家把窗口拖离贴合位置（超过阈值）→ 手动拉开分离
    const host = hostWindowId.value ? findWindow(hostWindowId.value) : null
    const win = selfWindowId ? findWindow(selfWindowId) : null
    if (host && win) {
      const bounds = computeAttachedBounds(host)
      const distance = Math.hypot(win.x - bounds.x, win.y - bounds.y)
      if (distance > DETACH_DRAG_DISTANCE) {
        detach()
        return
      }
    }
    // 未拉开：松手后由跟随循环拉回贴合位置
    return
  }

  const list = windowService?.windows.value
  if (!list || !selfWindowId) return
  const self = list.find((w) => w.id === selfWindowId)
  if (!self) return

  let best: WindowInstance | null = null
  let bestDist = Infinity
  for (const w of list) {
    if (w.id === selfWindowId) continue
    if (w.layer === 'ai' || w.mode === 'modal' || w.isMinimized) continue
    const dist = edgeDistance(self, w)
    if (dist < bestDist) {
      bestDist = dist
      best = w
    }
  }
  if (best && bestDist < ATTACH_THRESHOLD) {
    attachTo(best.id)
  }
}

/** 两窗口矩形的最近边距（重叠时为 0） */
function edgeDistance(a: WindowInstance, b: WindowInstance): number {
  const ax2 = a.x + a.width
  const ay2 = a.y + a.height
  const bx2 = b.x + b.width
  const by2 = b.y + b.height
  const dx = Math.max(a.x - bx2, b.x - ax2, 0)
  const dy = Math.max(a.y - by2, b.y - ay2, 0)
  return Math.hypot(dx, dy)
}

// ─── 摇动检测（拖动中采样） ─────────────────────────────

function handleAiDragMove(pos: { x: number; y: number }): void {
  isAiDragging = true
  if (!isAttached.value) return

  const now = performance.now()
  shakeSamples.push({ ...pos, t: now })
  while (shakeSamples.length && now - shakeSamples[0].t > SHAKE_WINDOW_MS) shakeSamples.shift()
  while (shakeSamples.length > SHAKE_SAMPLES) shakeSamples.shift()
  if (shakeSamples.length < 4) return

  // 统计 x/y 方向反转次数：快速往返达到阈值即判定为"摇动"
  let reversals = 0
  let prevDirX = 0
  let prevDirY = 0
  for (let i = 1; i < shakeSamples.length; i++) {
    const dx = shakeSamples[i].x - shakeSamples[i - 1].x
    const dy = shakeSamples[i].y - shakeSamples[i - 1].y
    const dirX = dx > 0 ? 1 : dx < 0 ? -1 : 0
    const dirY = dy > 0 ? 1 : dy < 0 ? -1 : 0
    if (dirX !== 0 && prevDirX !== 0 && dirX !== prevDirX) reversals += 1
    if (dirY !== 0 && prevDirY !== 0 && dirY !== prevDirY) reversals += 1
    if (dirX !== 0) prevDirX = dirX
    if (dirY !== 0) prevDirY = dirY
  }

  if (reversals >= SHAKE_THRESHOLD) {
    shakeSamples.length = 0
    suppressAttachOnce = true
    detach()
  }
}

// ─── 贴合跟随（rAF 轮询目标窗口几何） ────────────────────

function computeAttachedBounds(host: WindowInstance): { x: number; y: number; width: number; height: number } {
  // 贴合态尺寸固定（不随主窗口缩放变化），仅位置跟随主窗口
  const width = AI_CHAT_WIDTH
  const height = AI_CHAT_HEIGHT
  let x: number
  let y = host.y
  if (host.isMaximized) {
    // 目标全屏：贴屏幕右缘
    x = Math.max(0, window.innerWidth - width - EDGE_GAP)
  } else {
    x = host.x + host.width + EDGE_GAP
    if (x + width > window.innerWidth) {
      x = host.x - width - EDGE_GAP
    }
  }
  // 垂直与主窗口顶部对齐；超出屏幕底部时钳制在可视区内
  y = Math.max(0, Math.min(y, window.innerHeight - height))
  return { x: Math.max(0, x), y, width, height }
}

function applyAttachedBounds(): void {
  const host = hostWindowId.value ? findWindow(hostWindowId.value) : null
  if (!host) return
  updateSelfWindow({ ...computeAttachedBounds(host), resizable: false })
}

function startFollowLoop(): void {
  stopFollowLoop()
  const loop = () => {
    if (!isAttached.value) return
    const host = hostWindowId.value ? findWindow(hostWindowId.value) : null
    if (!host) {
      // 目标窗口被关闭 → 自动分离
      detach()
      return
    }
    const win = selfWindowId ? findWindow(selfWindowId) : null
    // 拖拽期间暂停跟随（避免与玩家拖动对抗），松手后自动回贴
    if (win && !isAiDragging) {
      const bounds = computeAttachedBounds(host)
      if (bounds.x !== win.x || bounds.y !== win.y || bounds.width !== win.width || bounds.height !== win.height) {
        updateSelfWindow({ ...bounds, resizable: false })
      }
      if (win.isMinimized !== host.isMinimized) {
        updateSelfWindow({ isMinimized: host.isMinimized })
      }
    }
    followRaf = requestAnimationFrame(loop)
  }
  followRaf = requestAnimationFrame(loop)
}

function stopFollowLoop(): void {
  if (followRaf) cancelAnimationFrame(followRaf)
  followRaf = 0
}

// ─── 对话播放（打字机 / 选项 / 跳转） ────────────────────

function playScript(nodes: AiNode[]): void {
  stopTyping()
  script.value = nodes.map((n, i) => ({ ...n, id: n.id ?? `node-${i}` }))
  nodeIndex.value = 0
  enterNode()
}

function enterNode(): void {
  const node = current.value
  if (!node) return
  node.effect?.()
  startTyping()
}

function startTyping(): void {
  const node = current.value
  if (!node) return
  typedText.value = ''
  if (node.expression) currentExpression.value = node.expression
  if (!node.text) {
    isTyping.value = false
    return
  }
  stopTyping()
  isTyping.value = true
  let cursor = 0
  typeTimer = setInterval(() => {
    cursor += 1
    typedText.value = node.text!.slice(0, cursor)
    if (cursor >= node.text!.length) stopTyping()
  }, TYPING_DELAY_MS)
}

function stopTyping(): void {
  if (typeTimer !== null) {
    clearInterval(typeTimer)
    typeTimer = null
  }
  isTyping.value = false
}

function goto(targetId?: string): void {
  if (targetId !== undefined) {
    const target = script.value.findIndex((n) => n.id === targetId)
    if (target !== -1) {
      nodeIndex.value = target
      enterNode()
      return
    }
  }
  if (nodeIndex.value < script.value.length - 1) {
    nodeIndex.value += 1
    enterNode()
  } else {
    // 剧本结束：停留当前表情与文本
    typedText.value = ''
    isTyping.value = false
  }
}

function handleChoice(choice: AiChoice): void {
  choice.effect?.()
  goto(choice.next)
}

function handleLinesClick(): void {
  const node = current.value
  if (!node) return
  if (isTyping.value) {
    typedText.value = node.text ?? ''
    stopTyping()
    return
  }
  if (node.choices) return
  goto(node.next)
}

// ─── 联动事件（目标窗口 → AI） ──────────────────────────

let aiEventOff: (() => void) | null = null

function handleAiEvent(event: string, payload: unknown, sourceWindowId: string): void {
  if (!isAttached.value || sourceWindowId !== hostWindowId.value) return
  if (event === 'puzzle-wrong') {
    const count = (payload as { count?: number } | undefined)?.count ?? 0
    if (count === 2) {
      playScript(buildPuzzleHintOffer())
    } else if (count >= 3) {
      playScript(buildPuzzleAutoFill())
    }
  }
}

/** 输错 2 次：AI 提供"帮开提示（-30 TVB）"选项 */
function buildPuzzleHintOffer(): AiNode[] {
  return [
    {
      id: 'wrong-2',
      expression: 'awkward',
      text: '……看你卡了半天。要不要我帮你把提示打开？一次 30 个 TVB。',
      choices: [
        {
          label: '帮我打开提示（-30 TVB）',
          effect: () => {
            if (creditsStore.spendVtb(AI_HINT_COST) && hostWindowId.value) {
              sendHostAction(hostWindowId.value, 'ai-open-hint')
            } else {
              playScript(buildInsufficientBalance())
            }
          },
          next: 'wrong-2-after',
        },
        { label: '我再想想', next: 'wrong-2-quiet' },
      ],
    },
    { id: 'wrong-2-after', expression: 'smile', text: '提示给你了。剩下你自己琢磨。' },
    { id: 'wrong-2-quiet', expression: 'normal', text: '……行，我看着。' },
  ]
}

/** 输错 3 次：AI 自动填入答案（不提交） */
function buildPuzzleAutoFill(): AiNode[] {
  return [
    {
      id: 'wrong-3',
      expression: 'urgent',
      text: '……我受够了。答案我帮你填好了，你自己核对一下再提交。',
      effect: () => {
        if (hostWindowId.value) sendHostAction(hostWindowId.value, 'ai-fill-answer')
      },
    },
    { id: 'wrong-3-end', expression: 'normal', text: '下次别这么磨蹭。' },
  ]
}

/** TVB 余额不足 */
function buildInsufficientBalance(): AiNode[] {
  return [{ id: 'no-credits', expression: 'annoy', text: '……你的 TVB 不够。先想办法赚点吧。' }]
}
</script>

<template>
  <section
    class="ai-assistant"
    :class="{ 'ai-assistant--attached': isAttached }"
    aria-label="AI Assistant"
  >
    <!-- 第二行：离开态图片占满；贴合态"左图右文"；无文字时大头照占满 -->
    <div
      class="ai-assistant__body"
      :class="{
        'ai-assistant__body--attached': isAttached,
        'ai-assistant__body--portrait': isPortraitMode,
      }"
    >
      <div class="ai-assistant__image-area" @click="handleImageClick">
        <canvas
          ref="canvasRef"
          class="ai-assistant__canvas"
          aria-label="Halftone dot rendering"
        />
      </div>

      <!-- 贴合态：右侧文字（大头照待机态时隐藏） -->
      <div v-if="isAttached && !isPortraitMode" class="ai-assistant__lines">
        <p class="ai-assistant__text" @click="handleLinesClick">
          {{ typedText }}<span v-if="isTyping" class="ai-assistant__cursor" aria-hidden="true">_</span>
        </p>
      </div>
    </div>

    <!-- 第三行（贴合态，大头照待机态隐藏）：选项 / 继续 -->
    <div v-if="isAttached && current?.choices" class="ai-assistant__choices">
      <button
        v-for="(choice, i) in current.choices.slice(0, MAX_AI_CHOICES)"
        :key="i"
        class="ai-assistant__choice"
        type="button"
        @click="handleChoice(choice)"
      >
        {{ choice.label }}
      </button>
    </div>

    <div v-else-if="isAttached && !isPortraitMode && !isTyping && current" class="ai-assistant__continue" @click="goto(current.next)">
      {{ t('aiChat.continue') }}
    </div>
  </section>
</template>

<style scoped>
.ai-assistant {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
}

/* 贴合态：窗口背景 75% 不透明（保证对话文字可读，颜色跟随主题） */
.ai-assistant--attached {
  background: rgba(20, 22, 30, 0.75);
  background: color-mix(in srgb, var(--surface-raised) 75%, transparent);
}

/* ── 第二行容器：离开态纵向（图片占满），贴合态横向（左图右文） ── */
.ai-assistant__body {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
}

.ai-assistant__body--attached {
  flex-direction: row;
}

/* "大头照"待机态：无聊天文字时图片占满整个内容区（覆盖贴合态左图右文） */
.ai-assistant__body--portrait {
  flex-direction: column;
}

.ai-assistant__body--portrait .ai-assistant__image-area {
  flex: 1;
  width: 100%;
  height: 100%;
}

/* 图片区：离开态占满整个 body；贴合态为左侧固定 128 方形（表情差分） */
.ai-assistant__image-area {
  position: relative;
  display: flex;
  min-height: 0;
  flex: 1;
  cursor: pointer;
}

.ai-assistant__body--attached .ai-assistant__image-area {
  flex: 0 0 128px;
  width: 128px;
  height: 128px;
}

.ai-assistant__canvas {
  width: 100%;
  height: 100%;
  display: block;
  user-select: none;
  -webkit-user-drag: none;
  transition: opacity 0.15s ease;
}

.ai-assistant__image-area:active .ai-assistant__canvas {
  opacity: 0.7;
}

/* 贴合态：右侧文字区 */
.ai-assistant__lines {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  border-left: 1px solid var(--line-subtle);
}

.ai-assistant__text {
  flex: 1;
  min-height: 0;
  margin: 0;
  padding: 10px 12px;
  overflow-y: auto;
  color: var(--text-primary);
  font: 12px/1.7 var(--font-ui);
  white-space: pre-wrap;
  word-break: break-word;
  cursor: pointer;
}

.ai-assistant__cursor {
  color: var(--signal-red-soft);
  animation: ai-cursor-blink 0.8s steps(1) infinite;
}

@keyframes ai-cursor-blink {
  0%, 49% { opacity: 1; }
  50%, 100% { opacity: 0; }
}

/* ── 第三行（贴合态）：选项 / 继续 ── */
.ai-assistant__choices {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px 10px;
  border-top: 1px solid var(--line-subtle);
}

.ai-assistant__choice {
  width: 100%;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: transparent;
  font: 600 11px var(--font-ui);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.ai-assistant__choice:hover {
  border-color: var(--signal-mint);
  color: var(--signal-mint);
  background: var(--surface-hover);
}

.ai-assistant__continue {
  padding: 8px 12px;
  border-top: 1px solid var(--line-subtle);
  color: var(--text-muted);
  font: 600 10px var(--font-mono);
  text-align: right;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  cursor: pointer;
  transition: color 0.12s;
}

.ai-assistant__continue:hover {
  color: var(--signal-mint);
}
</style>
