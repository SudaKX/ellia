<script setup lang="ts">
/**
 * # AI 助手浮动窗口内容组件
 *
 * 内嵌在 WindowFrame 中运行的 AI 助手面板。
 * 由 DesktopView 在 onMounted 时通过 windowService.send 创建，
 * 不经过 applicationRegistry 注册，因此不会出现在 Launchpad 和 DockBar 中。
 *
 * ## 交互设计
 *
 * - **点击图片**：轮换到下一张 kei 表情图片 + 轮换标题栏台词
 * - **关闭按钮**：在标题栏最右边（由 WindowFrame closeAction prop 接管），
 *   点击弹出 Permission Denied 模态弹窗
 * - **拖拽**：通过标题栏（WindowFrame 原生支持）
 *
 * ## 设计决策
 *
 * - **关闭按钮不放在内容区**：改用 WindowFrame 的 closeAction prop，
 *   在标题栏右侧渲染原生 X 按钮，点击走自定义回调而非默认关闭流程。
 * - **图片和台词同步轮换**：每次点击图片时同时推进图片索引和标题索引，
 *   标题通过 onSetTitle 回调更新到 WindowFrame 的 title prop。
 * - **图片列表和台词列表由 componentProps 传入**：方便后续调整素材，
 *   无需修改组件代码。
 *
 * ## 使用方式
 *
 * ```ts
 * componentProps: {
 *   images: ['/console/images/kei/normal1.webp', ...],
 *   titles: ['台词1', '台词2', '台词3'],
 *   onSetTitle: (text: string) => { aiTitle.value = text },
 * }
 * ```
 */

import { computed, ref } from 'vue'

const props = defineProps<{
  /** kei 表情图片 URL 数组，点击轮换 */
  images: string[]
  /** 标题栏台词数组，与图片同步轮换 */
  titles: string[]
  /** 更新标题栏文本的回调 */
  onSetTitle?: (text: string) => void
}>()

/** 当前图片索引 */
const currentIndex = ref(0)
const currentImage = computed(() => props.images[currentIndex.value] || props.images[0])

/**
 * 点击图片：轮换到下一张 + 更新标题栏台词。
 * 图片和台词独立循环，各自 wraparound。
 */
function handleClick() {
  currentIndex.value = (currentIndex.value + 1) % props.images.length
  // 标题台词与图片同步轮换（使用同一索引，确保一一对应）
  if (props.titles.length > 0) {
    const titleIndex = currentIndex.value % props.titles.length
    props.onSetTitle?.(props.titles[titleIndex])
  }
}
</script>

<template>
  <section class="ai-assistant" aria-label="AI Assistant">
    <!-- 图片：填满整个 body，点击轮换。object-fit: fill 确保无留白 -->
    <div class="ai-assistant__image-area" @click="handleClick">
      <img
        :src="currentImage"
        :alt="`Kei expression ${currentIndex + 1}`"
        class="ai-assistant__image"
        draggable="false"
        @dragstart.prevent
      />
    </div>
  </section>
</template>

<style scoped>
.ai-assistant {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--surface-panel);
}

/* 图片区域：填满整个 body 空间，无留白 */
.ai-assistant__image-area {
  flex: 1;
  display: flex;
  min-height: 0;
  cursor: pointer;
}

.ai-assistant__image {
  width: 100%;
  height: 100%;
  object-fit: fill;
  display: block;
  user-select: none;
  -webkit-user-drag: none;
  transition: opacity 0.15s ease;
}

/* 图片点击时的微小反馈 */
.ai-assistant__image-area:active .ai-assistant__image {
  opacity: 0.7;
}
</style>
