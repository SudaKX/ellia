<script setup lang="ts">
/**
 * # Live2DAssistant.vue — Live2D 虚拟形象窗口
 *
 * 将 Live2D 模型嵌入 FakeOS 窗口系统的 Vue 组件。
 * 负责 Vue 生命周期（挂载/卸载/点击事件），
 * 运行时逻辑委托给 `useLive2DAssistant` composable。
 *
 * ## Props
 *
 * - `modelUrl` — 模型 model3.json 的完整 URL
 * - `idleGroups` — 待机动作组名称列表
 * - `tapGroups` — 点击动作组名称列表
 * - `defaultScaleMultiplier` — 缩放倍数（默认 2）
 * - `positionRatio` — 模型中心比例坐标（默认 0.5, 0.5）
 * - `zoneMotionGroups` — 头/身体分区动作组映射
 * - `onSetTitle` — 动作名称回调（更新窗口标题栏）
 *
 * ## 生命周期
 *
 * ```
 * onMounted  → initialize runtime → ResizeObserver
 * onBeforeUnmount → ResizeObserver.disconnect → runtime.dispose
 * ```
 *
 * ## 为什么 Pixi canvas 不直接用 v-if 渲染
 *
 * PixiJS Application 有自己的 canvas 元素，通过 `replaceChildren()` 注入。
 * Vue 不应直接管理 Pixi 的 DOM，否则 destroy/recreate 会导致模型重新加载。
 */

import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useLive2DAssistant } from '@/composables/useLive2DAssistant'

const props = defineProps<{
  modelUrl: string
  idleGroups: string[]
  tapGroups: string[]
  defaultScaleMultiplier?: number
  positionRatio?: { x: number; y: number }
  renderAreaRatio?: { x: number; y: number; width: number; height: number }
  zoneMotionGroups?: Partial<Record<'head' | 'body', string[]>>
  onSetTitle?: (text: string) => void
}>()

/**
 * Cubism Core 运行时 URL。
 * 基于 Vite `BASE_URL` 构造，确保 dev/build 路径一致。
 */
const CORE_SCRIPT_URL = new URL(
  'live2d/live2dcubismcore.min.js',
  window.location.origin + import.meta.env.BASE_URL,
).toString()

/** 动作名 → 标题栏显示文本映射 */
const MOTION_TITLES: Record<string, string> = {
  idle: '待机中', idle1: '待机中', idle2: '待机中', idle3: '待机中',
  idle4: '待机中', idle5: '待机中', idle6: '待机中',
  main_1: '主动作 1', main_2: '主动作 2', main_3: '主动作 3',
  main_4: '主动作 4', main_5: '主动作 5',
  touch_body: '摸身体', touch_head: '摸头',
}

const stageRef = ref<HTMLElement | null>(null)
const loadingText = ref('Live2D 加载中...')
const loadError = ref<string | null>(null)
const isReady = ref(false)

let resizeObserver: ResizeObserver | null = null
let runtime: ReturnType<typeof useLive2DAssistant> | null = null

function resolveTitle(group: string | null) {
  if (!group) return '动作播放失败'
  return MOTION_TITLES[group] ?? '动作播放中'
}

/** 页面卸载时销毁全局缓存的 Live2D 实例 */
function handlePageUnload() {
  runtime?.disposeGlobal()
}

/**
 * 点击模型区域 → 根据命中区域播放对应动作。
 * 点击模型外部 → 轮播 tapGroups。
 */
async function handleClick(event: MouseEvent) {
  if (!runtime || !isReady.value || loadError.value) return
  const zone = runtime.resolveZoneByPoint(event.clientX, event.clientY)
  const group = zone
    ? await runtime.playMotionForZone(zone)
    : await runtime.playNextMotion()
  props.onSetTitle?.(resolveTitle(group))
}

onMounted(async () => {
  props.onSetTitle?.('待机中')

  if (!stageRef.value) {
    loadError.value = 'Live2D 容器初始化失败'
    props.onSetTitle?.('加载失败')
    return
  }

  runtime = useLive2DAssistant({
    container: stageRef.value,
    coreScriptUrl: CORE_SCRIPT_URL,
    defaultScaleMultiplier: props.defaultScaleMultiplier,
    idleGroups: props.idleGroups,
    modelUrl: props.modelUrl,
    positionRatio: props.positionRatio,
    renderAreaRatio: props.renderAreaRatio,
    tapGroups: props.tapGroups,
    zoneMotionGroups: props.zoneMotionGroups,
  })

  await runtime.initialize()
  isReady.value = runtime.ready.value
  loadError.value = runtime.error.value

  if (loadError.value) {
    loadingText.value = loadError.value
    props.onSetTitle?.('加载失败')
    return
  }

  resizeObserver = new ResizeObserver(() => runtime?.resize())
  resizeObserver.observe(stageRef.value)

  // 页面卸载时彻底销毁全局缓存的 Live2D 实例
  window.addEventListener('beforeunload', handlePageUnload)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handlePageUnload)
  resizeObserver?.disconnect()
  runtime?.dispose()
})
</script>

<template>
  <section
    class="live2d-assistant"
    :class="{ 'live2d-assistant--interactive': isReady && !loadError }"
    aria-label="Live2D Assistant"
    @click="handleClick"
  >
    <div ref="stageRef" class="live2d-assistant__stage"></div>

    <!-- 加载/错误遮罩 -->
    <div v-if="!isReady || loadError" class="live2d-assistant__overlay">
      <p class="live2d-assistant__message">{{ loadError ?? loadingText }}</p>
    </div>
  </section>
</template>

<style scoped>
.live2d-assistant {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  /* 暗色渐变背景，模拟 AI 助手的科技感 */
  background:
    radial-gradient(circle at top, rgb(255 255 255 / 12%), transparent 45%),
    linear-gradient(180deg, rgb(14 23 40 / 88%), rgb(8 12 23 / 96%));
}

.live2d-assistant--interactive {
  cursor: pointer;
}

.live2d-assistant__stage {
  height: 100%;
  min-height: 0;
}

.live2d-assistant__overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(7 12 22 / 52%);
  backdrop-filter: blur(6px);
}

.live2d-assistant__message {
  margin: 0;
  color: rgb(229 236 255 / 92%);
  font-size: 0.92rem;
  letter-spacing: 0.04em;
  text-align: center;
}
</style>
