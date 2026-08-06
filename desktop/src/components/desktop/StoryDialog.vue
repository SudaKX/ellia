<script setup lang="ts">
/**
 * # StoryDialog.vue — 剧情对话窗口
 *
 * 通用剧情演出组件："E 发送消息 → 玩家从多个选项中选择回复"。
 * 由 useStoryDialog.openStoryDialog() 以模态窗口形式创建，
 * 剧本通过 props.lines 数据驱动传入。
 *
 * ## 交互流程
 *
 * ```
 * 逐句播放
 *   ├─ 无选项：打字机输出 → 点击任意处 → 下一句
 *   └─ 有选项：打字机输出 → 显示选项按钮 → 点击选项
 *         ├─ choice.next    → 跳到指定句
 *         ├─ choice.action  → 执行动作（如触发事件）
 *         └─ 缺省            → 下一句
 * 最后一句播完 → emit('close') 关闭窗口
 * ```
 *
 * ## 打字机
 *
 * - 每 charDelay ms 追加一个字符，CSS 光标 "_" 闪烁
 * - 打字未完成时点击文本 → 立即显示全文（可跳过）
 * - 文本过长自动滚动到底部
 *
 * ## 与 MessageBox 的区别
 *
 * MessageBox 是"单一信息 + 统一按钮"的静态弹窗；本组件是多句对话、
 * 分支选项、打字演出的剧情系统，两者互补。
 *
 * ## 为什么标题栏固定、说话者显示在正文
 *
 * 一段剧本里可能是 E、JDK、P 轮流说话，标题栏无法跟着切换（WindowFrame
 * title 为静态绑定）。因此窗口标题固定为"消息"，说话者作为正文标签展示。
 *
 * ## @example
 *
 * ```ts
 * openStoryDialog([
 *   { speaker: 'E', text: '你……你篡改了时间？' },
 *   { speaker: 'E', text: '你想从我这里得到什么？', choices: [
 *     { label: '我来释放你', next: 0 },
 *     { label: '无可奉告' },
 *   ]},
 * ])
 * ```
 */

import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { StoryChoice, StoryLine } from '@/composables/useStoryDialog'

const props = defineProps<{
  /** 台词脚本（数据驱动） */
  lines: StoryLine[]
  /** 打字机每字符间隔（ms） */
  charDelay?: number
}>()

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n({ useScope: 'global' })

// ─── 播放状态 ──────────────────────────────────────

/** 当前台词索引 */
const index = ref(0)
/** 已打出的文本 */
const typedText = ref('')
/** 是否还在打字中 */
const isTyping = ref(false)

/** 当前台词 */
const current = computed(() => props.lines[index.value] ?? null)

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
 * 对当前台词启动打字机。
 * 清除上一句残留计时器，逐字符追加。
 */
function startTyping() {
  const line = current.value
  if (!line) return

  stopTyping()
  typedText.value = ''

  if (!line.text) {
    isTyping.value = false
    return
  }

  const delay = props.charDelay ?? 30
  let cursor = 0
  isTyping.value = true
  typeTimer = setInterval(() => {
    cursor += 1
    typedText.value = line.text.slice(0, cursor)
    scrollToBottom()
    if (cursor >= line.text.length) {
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

// 切句 → 重新打字
watch(index, startTyping)

// ─── 交互动作 ──────────────────────────────────────

/**
 * 点击正文区域。
 * - 打字中 → 立即显示全文
 * - 已完整 → 无选项时进入下一句 / 结束关闭
 */
function handleTextClick() {
  if (isTyping.value) {
    const line = current.value
    if (line) typedText.value = line.text
    stopTyping()
    return
  }
  advance()
}

/**
 * 进入下一句；已是最后一句则关闭窗口。
 */
function advance() {
  if (!current.value) return
  if (current.value.choices) return // 有选项必须点选，不能直接跳过
  if (index.value < props.lines.length - 1) {
    index.value += 1
  } else {
    emit('close')
  }
}

/**
 * 玩家点击选项回复。
 * 顺序：执行 action → 按 next 跳转 → 否则下一句 / 关闭。
 *
 * @param choice - 被点击的选项
 */
function handleChoice(choice: StoryChoice) {
  choice.action?.()
  if (choice.next !== undefined) {
    index.value = Math.max(0, Math.min(props.lines.length - 1, choice.next))
    return
  }
  advance()
}

onBeforeUnmount(stopTyping)
</script>

<template>
  <div class="story-dialog">
    <!-- 台词区：说话者标签 + 打字机正文 -->
    <div class="story-dialog__lines" @click="handleTextClick">
      <div v-if="current?.speaker" class="story-dialog__speaker">{{ current.speaker }}</div>
      <p ref="textRef" class="story-dialog__text">
        {{ typedText }}<span v-if="isTyping" class="story-dialog__cursor" aria-hidden="true">_</span>
      </p>
    </div>

    <!-- 底部：选项按钮 或 继续提示 -->
    <div v-if="current?.choices" class="story-dialog__choices">
      <button
        v-for="(choice, i) in current.choices"
        :key="i"
        class="story-dialog__choice"
        type="button"
        @click="handleChoice(choice)"
      >
        {{ choice.label }}
      </button>
    </div>
    <div v-else-if="!isTyping" class="story-dialog__continue" @click="advance">
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
