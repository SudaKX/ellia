<script setup lang="ts">
/**
 * # ExampleCipher — 凯撒密码谜题（示例）
 *
 * 一个简单的凯撒密码解密谜题，展示如何使用 puzzle 开发 API。
 *
 * ## 谜题内容
 *
 * 明文被偏移 3 位加密："khoor zruog" → "hello world"
 * 玩家需要输入解密后的文本。
 *
 * ## 如何使用 puzzle API
 *
 * ```ts
 * const { state, submitAnswer, requestHint, hints } = usePuzzle('caesar-cipher', 'hello world')
 * ```
 *
 * ## 提示系统
 *
 * 谜题内置 2 条提示，玩家每次点击"提示"按钮揭示一条。
 * 提示内容通过 i18n 管理，支持多语言。
 *
 * @example
 * ```
 * > sil caesar-cipher
 * Opening puzzle: caesar-cipher ...
 * （桌面出现凯撒密码谜题窗口）
 * ```
 */

import { computed, inject, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { notifyAi, onHostAction } from '@/ai/useAiLiaison'
import { usePuzzle } from '@/composables/usePuzzle'
import { WINDOW_FRAME_ID } from '@/composables/windowFrameId'

const { t } = useI18n({ useScope: 'global' })

/** 谜题唯一 ID（与 registerPuzzle 中的 id 对应） */
const PUZZLE_ID = 'caesar-cipher'
/** 正确答案 */
const ANSWER = 'hello world'

const { state, submitAnswer, requestHint, hintCount } = usePuzzle(PUZZLE_ID, ANSWER)

/** 提示列表（i18n key 数组） */
const hintKeys = [
  'puzzles.caesarCipher.hint1',
  'puzzles.caesarCipher.hint2',
]

/** 已揭示的提示文本 */
const displayedHints = ref<string[]>([])

/** 用户输入 */
const userInput = ref('')

/** 是否已经验证过（用于显示"答案错误"提示） */
const hasAttempted = ref(false)

/** 是否已解决 */
const isSolved = computed(() => state.value === 'solved')

/** 连续输错次数（联动 AI：输错 2 次 AI 可帮开提示，3 次自动填答案） */
const wrongCount = ref(0)

/** 自身窗口 id（由 WindowFrame provide），用于 AI 联动路由 */
const selfWindowId = inject<string | null>(WINDOW_FRAME_ID, null)

/** 订阅 AI 操作（AI 侧已扣 TVB） */
const offHostAction = selfWindowId
  ? onHostAction(selfWindowId, (action) => {
      if (action === 'ai-open-hint') {
        const aiHint = t('puzzles.caesarCipher.aiHint')
        if (!displayedHints.value.includes(aiHint)) {
          displayedHints.value.push(aiHint)
        }
      } else if (action === 'ai-fill-answer') {
        // AI 自动填入答案（不自动提交，由玩家核对后提交）
        userInput.value = 'hello world'
      }
    })
  : null

onBeforeUnmount(() => {
  offHostAction?.()
})

function handleSubmit() {
  const correct = submitAnswer(userInput.value)
  if (!correct) {
    hasAttempted.value = true
    // 上报输错事件（AI 感知：2 次给提示选项，3 次自动填答案）
    wrongCount.value += 1
    if (selfWindowId) {
      notifyAi(selfWindowId, 'puzzle-wrong', { count: wrongCount.value })
    }
    return
  }
  // 解谜成功：重置错误计数并通知 AI
  wrongCount.value = 0
  if (selfWindowId) {
    notifyAi(selfWindowId, 'puzzle-solved')
  }
}

function handleHint() {
  const rawHints = hintKeys.map((k) => t(k))
  const hint = requestHint(rawHints)
  if (hint) {
    displayedHints.value.push(hint)
  }
}
</script>

<template>
  <div class="puzzle">
    <header class="puzzle__header">
      <p class="puzzle__eyebrow">{{ t('puzzles.label') }}</p>
      <h2 class="puzzle__title">{{ t('puzzles.caesarCipher.title') }}</h2>
    </header>

    <!-- 谜题描述 -->
    <p class="puzzle__description">
      {{ t('puzzles.caesarCipher.description') }}
    </p>

    <!-- 密文展示 -->
    <div class="puzzle__cipher">
      <span class="puzzle__cipher-label">{{ t('puzzles.caesarCipher.cipherLabel') }}</span>
      <code class="puzzle__cipher-text">khoor zruog</code>
    </div>

    <!-- 输入区（未解决时显示） -->
    <div v-if="!isSolved" class="puzzle__input-area">
      <input
        v-model="userInput"
        class="puzzle__input"
        type="text"
        :placeholder="t('puzzles.caesarCipher.placeholder')"
        @keydown.enter="handleSubmit"
      />
      <button class="puzzle__btn" type="button" @click="handleSubmit">
        {{ t('puzzles.submit') }}
      </button>
      <button
        v-if="hintCount < hintKeys.length"
        class="puzzle__btn puzzle__btn--hint"
        type="button"
        @click="handleHint"
      >
        {{ t('puzzles.hint') }}
      </button>
    </div>

    <!-- 错误提示 -->
    <p v-if="hasAttempted && !isSolved" class="puzzle__error">
      {{ t('puzzles.wrongAnswer') }}
    </p>

    <!-- 已解决状态 -->
    <div v-if="isSolved" class="puzzle__solved">
      <span class="puzzle__solved-icon">{{ t('puzzles.solvedIcon') }}</span>
      {{ t('puzzles.solved') }}
    </div>

    <!-- 已揭示的提示 -->
    <ul v-if="displayedHints.length > 0" class="puzzle__hints">
      <li v-for="(hint, i) in displayedHints" :key="i" class="puzzle__hint-item">
        {{ hint }}
      </li>
    </ul>
  </div>
</template>

<style scoped>
.puzzle {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px;
  min-height: 100%;
}

.puzzle__header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.puzzle__eyebrow {
  margin: 0;
  color: var(--signal-red-soft);
  font: 700 10px var(--font-mono);
  text-transform: uppercase;
}

.puzzle__title {
  margin: 0;
  color: var(--text-primary);
  font: 600 16px var(--font-ui);
}

.puzzle__description {
  margin: 0;
  color: var(--text-secondary);
  font: 13px/1.6 var(--font-ui);
}

.puzzle__cipher {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--canvas);
  border: 1px solid var(--line-default);
}

.puzzle__cipher-label {
  color: var(--text-muted);
  font: 11px var(--font-mono);
  flex-shrink: 0;
}

.puzzle__cipher-text {
  color: var(--text-primary);
  font: 18px/1.4 var(--font-mono);
  letter-spacing: 2px;
}

.puzzle__input-area {
  display: flex;
  gap: 8px;
  align-items: center;
}

.puzzle__input {
  flex: 1;
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: var(--surface-panel);
  font: 13px var(--font-mono);
  outline: none;
  transition: border-color 0.12s;
}

.puzzle__input:focus {
  border-color: var(--signal-red-soft);
}

.puzzle__btn {
  min-height: 34px;
  padding: 0 16px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: var(--surface-panel);
  font: 12px var(--font-ui);
  cursor: pointer;
  white-space: nowrap;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.puzzle__btn:hover {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}

.puzzle__btn--hint {
  border-style: dashed;
}

.puzzle__error {
  margin: 0;
  color: var(--signal-red);
  font: 12px var(--font-ui);
}

.puzzle__solved {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--canvas);
  border: 1px solid var(--signal-mint);
  color: var(--signal-mint);
  font: 600 14px var(--font-ui);
}

.puzzle__solved-icon {
  font-size: 18px;
}

.puzzle__hints {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.puzzle__hint-item {
  padding: 8px 12px;
  background: var(--canvas);
  border-left: 2px solid var(--signal-red-soft);
  color: var(--text-secondary);
  font: 12px var(--font-ui);
}
</style>
