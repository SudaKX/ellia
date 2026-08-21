<script setup lang="ts">
/**
 * # StoryDialog.vue — 交互剧情窗口（播放引擎）
 *
 * 配合 useStoryDialog.playStoryScript() 使用，按 StoryNode 数据驱动播放：
 * 打字机对白、玩家选项（≤4）、滑杆调节、按 id 跳转、节点副作用。
 *
 * ## 播放状态机
 *
 * ```
 * 进入节点（index 变化）
 *   ├─ 触发 node.effect()（成就/音频等副作用）
 *   ├─ 重置打字机（text 逐字输出；无 text 直接完成）
 *   └─ 交互区渲染：
 *        ├─ choices（1~4 个按钮）→ 点击 → choice.effect() + 跳转 choice.next
 *        ├─ slider（滑杆 + 提交） → 提交 → slider.effect(v) + 跳转 slider.next(v)
 *        └─ 无交互 → 点击继续 → 跳转 node.next
 * 越界（无目标节点）→ emit('close') 关闭窗口
 * ```
 *
 * ## 跳转规则（goto）
 *
 * 优先按目标节点 id 定位；id 不存在或缺失 → 顺序下一个节点；已是最后 → 关闭。
 * 因此创作者可只给关键分支命名 id，普通对白靠顺序自然衔接。
 *
 * ## 约束执行
 *
 * 选项超过 4 个时仅渲染前 4 个（useStoryDialog 已在服务层告警）。
 * choices 与 slider 互斥（脚本层约束），本组件按 choices 优先渲染。
 */

import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { StoryChoice, StoryNode } from '@/composables/useStoryDialog'
import { MAX_CHOICES } from '@/composables/useStoryDialog'

const props = defineProps<{
  /** 已归一化的剧情节点（id 保证存在） */
  nodes: StoryNode[]
  /** 打字机每字符间隔（ms） */
  charDelay?: number
}>()

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n({ useScope: 'global' })

// ─── 播放状态 ──────────────────────────────────────

/** 当前节点在脚本中的顺序索引 */
const index = ref(0)
/** 已打出的文本 */
const typedText = ref('')
/** 是否还在打字中 */
const isTyping = ref(false)
/** 滑杆当前值 */
const sliderValue = ref(0)

/** 当前节点 */
const current = computed(() => props.nodes[index.value] ?? null)

let typeTimer: ReturnType<typeof setInterval> | null = null

/** 终止打字定时器 */
function stopTyping() {
  if (typeTimer !== null) {
    clearInterval(typeTimer)
    typeTimer = null
  }
  isTyping.value = false
}

/**
 * 对当前节点启动打字机。
 * 无 text 的纯交互节点（仅 slider/choices）直接视为完成。
 */
function startTyping() {
  const node = current.value
  if (!node) return

  typedText.value = ''
  if (!node.text) {
    isTyping.value = false
    return
  }

  const delay = props.charDelay ?? 30
  let cursor = 0
  isTyping.value = true
  typeTimer = setInterval(() => {
    cursor += 1
    typedText.value = node.text!.slice(0, cursor)
    scrollToBottom()
    if (cursor >= node.text!.length) {
      stopTyping()
    }
  }, delay)
}

/** 文本容器滚动到底部（长文本时保持可见） */
const textRef = ref<HTMLElement | null>(null)
async function scrollToBottom() {
  await nextTick()
  const el = textRef.value
  if (el) el.scrollTop = el.scrollHeight
}

/**
 * 节点进入处理：触发副作用 → 重置滑杆 → 打字。
 * 用 immediate watch，让首个节点也走同一流程。
 */
function handleNodeEnter() {
  const node = current.value
  if (!node) return

  stopTyping()

  // 重置滑杆到初始值（缺省 = 区间中点）
  if (node.slider) {
    sliderValue.value = node.slider.initial ?? Math.round((node.slider.min + node.slider.max) / 2)
  }

  // 节点副作用（解锁成就、播放音频等）
  node.effect?.()

  startTyping()
}

watch(index, handleNodeEnter, { immediate: true })

// ─── 跳转 ──────────────────────────────────────────

/**
 * 跳转到目标节点。
 * 优先按 id 定位；目标缺失 → 顺序下一个；已是最后 → 关闭窗口。
 *
 * @param targetId - 目标节点 id；缺省 = 顺序下一个
 */
function goto(targetId?: string) {
  if (targetId !== undefined) {
    const target = props.nodes.findIndex((n) => n.id === targetId)
    if (target !== -1) {
      index.value = target
      return
    }
  }
  if (index.value < props.nodes.length - 1) {
    index.value += 1
  } else {
    emit('close')
  }
}

// ─── 交互动作 ──────────────────────────────────────

/**
 * 点击正文区域。
 * - 打字中 → 立即显示全文
 * - 已完整且无交互（无 choices/slider）→ 继续
 */
function handleLinesClick() {
  const node = current.value
  if (!node) return

  if (isTyping.value) {
    typedText.value = node.text ?? ''
    stopTyping()
    return
  }
  // 有交互节点的正文点击不推进，等待玩家操作
  if (node.choices || node.slider) return
  goto(node.next)
}

/**
 * 玩家点击选项回复。
 * 顺序：执行选项副作用 → 按 next 跳转。
 *
 * @param choice - 被点击的选项
 */
function handleChoice(choice: StoryChoice) {
  choice.effect?.()
  goto(choice.next)
}

/** 提交滑杆值：副作用 + 按值返回的目标 id 跳转 */
function handleSliderSubmit() {
  const node = current.value
  if (!node?.slider) return
  node.slider.effect?.(sliderValue.value)
  goto(node.slider.next(sliderValue.value))
}

onBeforeUnmount(stopTyping)
</script>

<template>
  <div class="story-dialog">
    <!-- 台词区：配图 + 说话者标签 + 打字机正文 -->
    <div class="story-dialog__lines" @click="handleLinesClick">
      <div v-if="current?.image" class="story-dialog__image-wrapper">
        <img :src="current.image" class="story-dialog__image" alt="story illustration" />
      </div>
      <div v-if="current?.speaker" class="story-dialog__speaker">{{ current.speaker }}</div>
      <p v-if="current?.text" ref="textRef" class="story-dialog__text">
        {{ typedText }}<span v-if="isTyping" class="story-dialog__cursor" aria-hidden="true">_</span>
      </p>
    </div>

    <!-- 底部交互区：选项（≤4）/ 滑杆 / 继续 -->
    <div v-if="current?.choices" class="story-dialog__choices">
      <button
        v-for="(choice, i) in current.choices.slice(0, MAX_CHOICES)"
        :key="i"
        class="story-dialog__choice"
        type="button"
        @click="handleChoice(choice)"
      >
        {{ choice.label }}
      </button>
    </div>

    <div v-else-if="current?.slider" class="story-dialog__slider">
      <div class="story-dialog__slider-row">
        <span class="story-dialog__slider-label">{{ current.slider.label }}</span>
        <input
          v-model.number="sliderValue"
          class="story-dialog__slider-input"
          type="range"
          :min="current.slider.min"
          :max="current.slider.max"
          :step="current.slider.step ?? 1"
          :aria-label="current.slider.label"
        />
        <span class="story-dialog__slider-value">{{ sliderValue }}</span>
      </div>
      <button
        class="story-dialog__choice story-dialog__slider-submit"
        type="button"
        @click="handleSliderSubmit"
      >
        {{ current.slider.submitLabel ?? t('story.dialog.submit') }}
      </button>
    </div>

    <div v-else-if="!isTyping" class="story-dialog__continue" @click="goto(current?.next)">
      {{ t('story.dialog.continue') }}
    </div>
  </div>
</template>

<style scoped>
.story-dialog {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  background: var(--canvas);
}

/* ── 台词区 ── */
.story-dialog__lines {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 18px;
  cursor: pointer;
}

.story-dialog__image-wrapper {
  margin-bottom: 12px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.story-dialog__image {
  max-width: 100%;
  max-height: 240px;
  object-fit: contain;
  border-radius: 4px;
}

.story-dialog__speaker {
  margin-bottom: 8px;
  color: var(--signal-mint);
  font: 700 11px var(--font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.story-dialog__text {
  margin: 0;
  color: var(--text-primary);
  font: 13px/1.7 var(--font-ui);
  white-space: pre-wrap;
  word-break: break-word;
}

.story-dialog__cursor {
  color: var(--signal-red-soft);
  animation: cursor-blink 0.8s steps(1) infinite;
}

@keyframes cursor-blink {
  0%, 49% { opacity: 1; }
  50%, 100% { opacity: 0; }
}

/* ── 底部操作区 ── */
.story-dialog__choices {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--line-subtle);
}

.story-dialog__choice {
  min-width: 96px;
  min-height: 32px;
  padding: 0 14px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: transparent;
  font: 600 11px var(--font-ui);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.story-dialog__choice:hover {
  border-color: var(--signal-mint);
  color: var(--signal-mint);
  background: var(--surface-hover);
}

/* ── 滑杆区 ── */
.story-dialog__slider {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-top: 1px solid var(--line-subtle);
}

.story-dialog__slider-row {
  display: flex;
  flex: 1;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.story-dialog__slider-label {
  flex-shrink: 0;
  color: var(--text-secondary);
  font: 600 11px var(--font-ui);
}

.story-dialog__slider-input {
  flex: 1;
  min-width: 0;
  height: 16px;
  accent-color: var(--signal-mint);
  cursor: pointer;
}

.story-dialog__slider-value {
  flex-shrink: 0;
  min-width: 32px;
  color: var(--signal-mint);
  font: 700 12px var(--font-mono);
  text-align: right;
}

.story-dialog__slider-submit {
  flex-shrink: 0;
}

.story-dialog__continue {
  padding: 10px 16px;
  border-top: 1px solid var(--line-subtle);
  color: var(--text-muted);
  font: 600 10px var(--font-mono);
  text-align: right;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  cursor: pointer;
  transition: color 0.12s;
}

.story-dialog__continue:hover {
  color: var(--signal-mint);
}
</style>
