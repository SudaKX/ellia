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
 *   点击人物图轮换 ellia 表情/台词/语音；拖动结束若靠近某普通窗口边缘 → 贴合。
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
  /** ellia 表情图片 URL 数组，点击轮换（离开态） */
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

// 声明 close 为自定义事件，避免 WindowFrame 透传的 @close 因组件多根节点无法继承而刷 Vue 警告
defineEmits<{
  close: []
}>()

const { t } = useI18n({ useScope: 'global' })
const audioService = useAudioService()
/**
 * ellia 立绘头部裁切（正方形区域，相对原图比例 0~1）：
 * 原图 1668×2388；头部内容范围像素约 426,172 → 1270,906（宽 844 × 高 734）。
 * 正方形 734×734 无法同时容纳头部左右缘（844 宽），裁切窗口整体向左收
 * （左缘 481→428、右缘 1215→1162），使头部在窗口内视觉居中：
 * 等效于画面右移约 40 CSS px，同时消除左侧立绘留白，不产生平移空白。
 */
const ELLIA_HEAD_CROP = {
  x: 428 / 1668,
  y: 172 / 2388,
  width: 734 / 1668,
  height: 734 / 2388,
}
const halftone = useHalftone({ dotSpacing: 3, maxRadius: 2.5, minRadius: 0.6, crop: ELLIA_HEAD_CROP })
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
/** 贴合缝隙"数据流光"特效层（Teleport 到 desktop-workspace，随窗口几何更新位置） */
const gapEl = ref<HTMLDivElement | null>(null)
/** 缝隙光点带：出发位置在目标窗口贴合边全高均匀分布，到达位置保持密集带分布 */
const gapDots = ref<{ yStart: number; dy: number; delay: number }[]>([])

/** 密集带区间：上缘 12.5%、下缘 25%（区域高度比例，顶 0% 底 100%） */
const DOT_BAND_TOP = 0.125
const DOT_BAND_BOTTOM = 0.25
/** 已生成点带的几何签名（区域高度），变化时重新分布 */
let lastDotGen = ''

/**
 * 生成光点带：
 * - 出发位置（yStart，区域高度百分比 0~100）：目标窗口贴合边全高均匀分布
 * - 到达位置：全部落在固定密集带（12.5%~25%）
 * - dy：从出发到到达的垂直位移（px），由区域高度换算，动画做斜线汇聚流动
 *
 * @param rectHeight 缝隙区域高度（px），用于把百分比位移换算成像素
 */
function spawnGapDots(rectHeight: number): void {
  gapDots.value = Array.from({ length: 34 }, (_, i) => {
    // 出发：全高均匀
    const yStart = Math.random() * 100
    // 到达：全部进入密集带
    const yEnd = (DOT_BAND_TOP + Math.random() * (DOT_BAND_BOTTOM - DOT_BAND_TOP)) * 100
    const dy = rectHeight > 0 ? ((yEnd - yStart) / 100) * rectHeight : 0
    // 相邻点小幅错开相位，保持"点带"整体流动感的同时有细微粒子流质感
    const delay = (i % 5) * 0.09 + Math.random() * 0.18
    return { yStart, dy, delay }
  })
}
const isTyping = ref(false)
const currentExpression = ref<AiExpression>('normal')
const hostTitle = ref('')
/**
 * "大头照"待机态：剧本结束 / 无对白节点时表情大图占满内容区。
 * 防抖：typedText 为空先等 PORTRAIT_DEBOUNCE_MS，仍为空才变大，
 * 避免跳转下一段文字瞬间 typedText 被清空导致一闪。
 */
const isPortraitMode = ref(false)
/** 大头照防抖定时器 */
let portraitTimer: ReturnType<typeof setTimeout> | null = null

/** typedText 清空后进入大头照的等待时长（ms） */
const PORTRAIT_DEBOUNCE_MS = 200

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
    // 图片渲染失败不能中断后续通信回调注册（贴合/分离按钮、拖拽检测、联动事件）
    await halftone.render(displayImage.value).catch(() => undefined)
  }

  // 注册与 DesktopView 的通信回调（标题栏贴合/分离按钮 + 拖拽检测）
  registerAiDetach(() => detach())
  registerAiAttach(() => handleAttachBtn())
  registerAiDragHandlers({ onDragMove: handleAiDragMove, onDragEnd: handleAiDragEnd })

  // 订阅目标窗口联动事件
  aiEventOff = onAiEvent(handleAiEvent)
})

onBeforeUnmount(() => {
  clearTimeout(portraitTimer ?? undefined)
  portraitTimer = null
  halftone.destroy()
  stopTyping()
  stopFollowLoop()
  aiEventOff?.()
})

watch(displayImage, (url) => {
  halftone.render(url).catch(() => undefined)
})

// 切换贴合/离开时窗口尺寸变化，等布局稳定后重绘点阵
watch(liaisonState, () => {
  nextTick(() => halftone.render(displayImage.value).catch(() => undefined))
})

// 大头照防抖：typedText 为空（剧本结束/无对白节点）先等 200ms，仍为空才进入
// 大头照模式；有文字或有选项立即退出。避免跳转下一段时 typedText 清空的瞬间闪一下。
watch([typedText, () => current.value?.choices, isAttached], () => {
  clearTimeout(portraitTimer ?? undefined)
  if (!isAttached.value) {
    isPortraitMode.value = false
    return
  }
  if (typedText.value || current.value?.choices) {
    isPortraitMode.value = false
    return
  }
  portraitTimer = setTimeout(() => {
    portraitTimer = null
    if (isAttached.value && !typedText.value && !current.value?.choices) {
      isPortraitMode.value = true
    }
  }, PORTRAIT_DEBOUNCE_MS)
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

/**
 * 贴合缝隙"数据流光"：根据两窗口几何计算缝隙条带的位置与流向。
 * 区域 = 两窗口贴合边的并集高度，clip-path 裁成"四角相连"的梯形：
 * host 贴合边的上下两角 ↔ AI 贴合边的上下两角。
 * 数据从目标窗口流向 AI 窗口（右贴 → 光点左→右，左贴 → 反向）。
 * 内部重新读取最新窗口几何，避免拿到本帧更新前的旧值。
 */
function updateGapEffects(host: WindowInstance | null): void {
  const gap = gapEl.value
  const aiWin = selfWindowId ? findWindow(selfWindowId) : null
  if (!gap || !host || !aiWin) return

  let gapLeft: number
  let gapWidth: number
  if (host.isMaximized) {
    // 目标全屏：AI 窗贴屏幕右缘，缝隙为右侧 EDGE_GAP 条带
    gapLeft = host.x + host.width - EDGE_GAP
    gapWidth = EDGE_GAP
  } else if (aiWin.x > host.x) {
    // 右贴：AI 窗在目标窗口右侧，缝隙 = host 右缘 → AI 左缘
    gapLeft = host.x + host.width
    gapWidth = aiWin.x - gapLeft
  } else {
    // 左贴：AI 窗在目标窗口左侧，缝隙 = AI 右缘 → host 左缘
    gapLeft = aiWin.x + aiWin.width
    gapWidth = host.x - gapLeft
  }
  gapWidth = Math.max(0, gapWidth)

  // 区域 = 两窗口贴合边的并集高度（含错位），clip-path 裁成"四角相连"的梯形
  const rectTop = Math.min(host.y, aiWin.y)
  const rectBottom = Math.max(host.y + host.height, aiWin.y + aiWin.height)
  const rectHeight = Math.max(0, rectBottom - rectTop)

  // 拖动中：位置即时跟随（禁过渡）；松手后：平滑回贴/跟随（避免瞬间跳变）。
  // 必须在几何更新之前设置 transition，否则同帧属性已更新完、过渡不会触发。
  // 【临时注释】去掉全部动画过渡，先看静态效果
  // gap.style.transition = isAiDragging
  //   ? 'none'
  //   : 'left 0.25s ease-out, top 0.25s ease-out, width 0.25s ease-out, height 0.25s ease-out, opacity 0.35s ease'

  gap.style.left = `${gapLeft}px`
  gap.style.top = `${rectTop}px`
  gap.style.width = `${gapWidth}px`
  gap.style.height = `${rectHeight}px`

  // 梯形顶点（相对元素左上角）
  const aiRight = aiWin.x > host.x
  const hostTopY = host.y - rectTop
  const hostBottomY = host.y + host.height - rectTop
  const aiTopY = aiWin.y - rectTop
  const aiBottomY = aiWin.y + aiWin.height - rectTop
  gap.style.clipPath = aiRight
    ? `polygon(0 ${hostTopY}px, 0 ${hostBottomY}px, ${gapWidth}px ${aiBottomY}px, ${gapWidth}px ${aiTopY}px)`
    : `polygon(0 ${aiTopY}px, 0 ${aiBottomY}px, ${gapWidth}px ${hostBottomY}px, ${gapWidth}px ${hostTopY}px)`

  gap.style.setProperty('--flow', aiRight ? '1' : '-1')
  // 任一窗口最小化（联动隐藏）时流光同步隐藏
  gap.style.visibility = host.isMinimized || aiWin.isMinimized ? 'hidden' : 'visible'

  // 惰性生成光点带：出发全高均匀、到达保持密集带；区域高度变化时重新分布
  const dotSig = `${rectHeight.toFixed(0)}`
  if (gapDots.value.length === 0 || dotSig !== lastDotGen) {
    lastDotGen = dotSig
    spawnGapDots(rectHeight)
  }
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
    // 缝隙流光位置随窗口几何实时更新（内部读取最新窗口几何）
    updateGapEffects(host)
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
  clearTimeout(portraitTimer ?? undefined)
  portraitTimer = null
  isPortraitMode.value = false
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
  // node.text 为 i18n key，先翻译再按字符逐字输出
  const displayText = t(node.text)
  let cursor = 0
  typeTimer = setInterval(() => {
    cursor += 1
    typedText.value = displayText.slice(0, cursor)
    if (cursor >= displayText.length) stopTyping()
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
    typedText.value = t(node.text ?? '')
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
      text: 'aiScripts.wrong2',
      choices: [
        {
          label: 'aiScripts.wrong2Open',
          effect: () => {
            if (creditsStore.spendVtb(AI_HINT_COST) && hostWindowId.value) {
              sendHostAction(hostWindowId.value, 'ai-open-hint')
            } else {
              playScript(buildInsufficientBalance())
            }
          },
          next: 'wrong-2-after',
        },
        { label: 'aiScripts.wrong2Think', next: 'wrong-2-quiet' },
      ],
    },
    { id: 'wrong-2-after', expression: 'smile', text: 'aiScripts.wrong2After' },
    { id: 'wrong-2-quiet', expression: 'normal', text: 'aiScripts.wrong2Quiet' },
  ]
}

/** 输错 3 次：AI 自动填入答案（不提交） */
function buildPuzzleAutoFill(): AiNode[] {
  return [
    {
      id: 'wrong-3',
      expression: 'urgent',
      text: 'aiScripts.wrong3',
      effect: () => {
        if (hostWindowId.value) sendHostAction(hostWindowId.value, 'ai-fill-answer')
      },
    },
    { id: 'wrong-3-end', expression: 'normal', text: 'aiScripts.wrong3End' },
  ]
}

/** TVB 余额不足 */
function buildInsufficientBalance(): AiNode[] {
  return [{ id: 'no-credits', expression: 'annoy', text: 'aiScripts.noCredits' }]
}
</script>

<template>
  <section
    class="ai-assistant"
    :class="{ 'ai-assistant--attached': isAttached }"
    aria-label="AI Assistant"
  >
    <!-- 第二行：离开态图片占满；贴合态"左图右文"；剧本结束/无对白时大头照占满 -->
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
        {{ t(choice.label) }}
      </button>
    </div>

    <div v-else-if="isAttached && !isPortraitMode && !isTyping && current" class="ai-assistant__continue" @click="goto(current.next)">
      {{ t('aiChat.continue') }}
    </div>
  </section>

  <!-- 贴合缝隙"数据流光"特效：Teleport 到桌面工作区（与窗口同一坐标系，避免状态栏偏移），
       显隐用 opacity 过渡，分离/贴合时淡入淡出而非瞬间消失 -->
  <Teleport to=".desktop-workspace">
    <div
      ref="gapEl"
      class="liaison-gap"
      :class="{ 'liaison-gap--off': !isAttached }"
      aria-hidden="true"
    >
      <!-- 光点带：从目标窗口贴合边全高均匀出发，斜线流到 AI 窗口侧密集带 -->
      <!-- 【临时注释】光点带（粒子）先隐藏
      <span
        v-for="(dot, i) in gapDots"
        :key="i"
        class="liaison-gap__dot"
        :style="{
          top: `${dot.yStart}%`,
          animationDelay: `${dot.delay}s`,
          '--flow-dy': `${dot.dy}px`,
        }"
      />
      -->
    </div>
  </Teleport>
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

/* "大头照"待机态：无聊天文字时图片占满整个内容区（覆盖贴合态左图右文） */
/* 注意：必须写在 .ai-assistant__body--attached 规则之后，同特异性下后者生效 */
.ai-assistant__body--portrait {
  flex-direction: column;
}

.ai-assistant__body--portrait .ai-assistant__image-area {
  flex: 1;
  width: 100%;
  height: 100%;
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

/* ── 贴合缝隙"数据流光"特效（Teleport 到 desktop-workspace 的覆盖层） ──
   与窗口处于同一坐标系（绝对定位），避免状态栏导致的视口偏移；
   clip-path 由 JS 实时裁成"两窗口四角相连"的梯形；
   颜色跟随主题（--signal-mint + color-mix），明/暗主题自动适配 */
.liaison-gap {
  position: absolute;
  z-index: 1000;
  pointer-events: none;
  overflow: hidden;
  opacity: 1;
  /* 淡入淡出（贴合/分离），位置过渡由 JS 每帧写入 inline */
  /* 【临时注释】 transition: opacity 0.35s ease; */
  /* 梯形内微弱的连接底色 */
  /* 【临时注释】光带底色先隐藏
  background: linear-gradient(
    90deg,
    transparent,
    color-mix(in srgb, var(--signal-mint) 14%, transparent),
    transparent
  );
  box-shadow: 0 0 8px 1px color-mix(in srgb, var(--signal-mint) 20%, transparent);
  */
}

.liaison-gap--off {
  opacity: 0;
}

/* 数据光点带：从目标窗口贴合边全高均匀出发，斜线流到 AI 窗口侧密集带（12.5%~25%） */
/* 【临时注释】粒子样式先隐藏
.liaison-gap__dot {
  position: absolute;
  left: 50%;
  width: 3px;
  height: 3px;
  margin-left: -1.5px;
  border-radius: 999px;
  background: var(--signal-mint);
  box-shadow: 0 0 5px 1px color-mix(in srgb, var(--signal-mint) 55%, transparent);
  animation: liaison-dot-flow 2.6s ease-in-out infinite;
  will-change: transform, opacity;
}
*/

/* 【临时注释】@keyframes liaison-dot-flow {
  0% {
    transform: translate(calc(-16px * var(--flow, 1)), 0);
    opacity: 0;
  }
  10% {
    opacity: 1;
  }
  90% {
    opacity: 1;
  }
  100% {
    transform: translate(calc(16px * var(--flow, 1)), var(--flow-dy, 0px));
    opacity: 0;
  }
}*/
</style>
