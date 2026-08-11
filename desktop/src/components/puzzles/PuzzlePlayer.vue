<script setup lang="ts">
/**
 * # PuzzlePlayer.vue — 通用题目窗口（数据驱动播放器）
 *
 * 渲染任意 PuzzleDefinition（见 types/puzzle.ts）的通用谜题窗口：
 * - 题面：富媒体块（文本 / 图片 / 视频 / 富文本 HTML）
 * - 题型：单选（2~10 项）/ 多选（2~10 项）/ 填空（一个或多个空）
 * - 交互：提交校验（usePuzzlePlayer）、错误反馈、逐条提示、答后解析
 *
 * ## 数据来源
 *
 * 通过 componentProps.puzzleId 传入，内部调用 usePuzzleLibrary.getPuzzleDefinition(id)
 * 获取定义——内置题（src/puzzles/data/）或出题器发布的远程题均可。
 *
 * ## solved 持久化
 *
 * 沿用 usePuzzle 的 localStorage 语义（ellia.puzzle.{id}），
 * 与旧谜题组件共享"已解决"状态。
 *
 * ## i18n
 *
 * 内置题的标题/文本/提示支持 titleKey / textKey / hintKeys 引用翻译；
 * 出题器出的题只用纯文本字段。
 */

import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getPuzzleDefinition } from '@/composables/usePuzzleLibrary'
import { checkPuzzleAnswer, readPuzzleSolved, writePuzzleSolved } from '@/composables/usePuzzlePlayer'
import type { ContentBlock } from '@/types/puzzle'

const props = defineProps<{
  /** 题目 id（.puz 文件名 / sil 参数） */
  puzzleId: string
}>()

const { t } = useI18n({ useScope: 'global' })

/** 题目定义（按 id 从题目库取） */
const definition = computed(() => getPuzzleDefinition(props.puzzleId))

// ─── 渲染辅助 ──────────────────────────────────────

/** 显示标题：titleKey 优先（内置题多语言），否则纯文本 */
const displayTitle = computed(() => {
  const def = definition.value
  if (!def) return ''
  return def.titleKey ? t(def.titleKey) : def.title
})

/** 文本块显示内容：textKey 优先（内置题多语言），否则纯文本 */
function blockText(block: Extract<ContentBlock, { type: 'text' }>): string {
  return block.textKey ? t(block.textKey) : block.text
}

/** 提示列表：hintKeys 优先（内置题多语言），否则纯文本 */
const hintList = computed(() => {
  const def = definition.value
  if (!def) return []
  return def.hintKeys ? def.hintKeys.map((key) => t(key)) : (def.hints ?? [])
})

// ─── 答题状态 ──────────────────────────────────────

/** 是否已解决（读取持久化状态） */
const isSolved = ref(readPuzzleSolved(props.puzzleId))
/** 已选项下标（single 单选替换 / multi 多选切换） */
const selectedIndices = ref<number[]>([])
/** 填空输入值（顺序对应 fillAnswers） */
const fillValues = ref<string[]>([])
/** 是否提交过（用于显示"答案错误"反馈） */
const hasAttempted = ref(false)
/** 已揭示的提示文本 */
const revealedHints = ref<string[]>([])
/** 加载失败的图片 url 集合（显示占位文本） */
const failedImages = ref<Set<string>>(new Set())

/** 填空输入框数量：fillAnswers 长度，缺失时 1 个 */
const fillCount = computed(() => definition.value?.fillAnswers?.length ?? 1)

/** 单选/多选选项切换 */
function toggleOption(index: number) {
  const def = definition.value
  if (!def) return
  if (def.type === 'single') {
    selectedIndices.value = [index]
    return
  }
  const current = selectedIndices.value
  selectedIndices.value = current.includes(index)
    ? current.filter((i) => i !== index)
    : [...current, index]
}

/** 提交答案 */
function handleSubmit() {
  const def = definition.value
  if (!def) return
  const correct = checkPuzzleAnswer(def, selectedIndices.value, fillValues.value)
  if (correct) {
    isSolved.value = true
    writePuzzleSolved(props.puzzleId)
    return
  }
  hasAttempted.value = true
}

/** 揭示下一条提示 */
function handleHint() {
  const all = hintList.value
  if (revealedHints.value.length >= all.length) return
  revealedHints.value.push(all[revealedHints.value.length])
}

/** 图片加载失败 → 标记占位 */
function handleImageError(url: string) {
  failedImages.value = new Set(failedImages.value).add(url)
}
</script>

<template>
  <div class="puzzle-player">
    <!-- 题目不存在 -->
    <p v-if="!definition" class="puzzle-player__not-found">{{ t('puzzles.notFound') }}</p>

    <template v-else>
      <header class="puzzle-player__header">
        <p class="puzzle-player__eyebrow">{{ t('puzzles.label') }}</p>
        <h2 class="puzzle-player__title">{{ displayTitle }}</h2>
      </header>

      <!-- 题面（富媒体块） -->
      <div class="puzzle-player__blocks">
        <template v-for="(block, i) in definition.blocks" :key="i">
          <!-- 文本 -->
          <p v-if="block.type === 'text' && block.variant !== 'code'" class="puzzle-player__text">
            {{ blockText(block) }}
          </p>
          <code v-else-if="block.type === 'text'" class="puzzle-player__code">
            {{ blockText(block) }}
          </code>

          <!-- 图片 -->
          <figure v-else-if="block.type === 'image'" class="puzzle-player__figure">
            <img
              v-if="!failedImages.has(block.url)"
              class="puzzle-player__image"
              :src="block.url"
              :alt="block.alt ?? block.caption ?? definition.title"
              loading="lazy"
              @error="handleImageError(block.url)"
            />
            <p v-else class="puzzle-player__image-fallback">
              {{ t('puzzles.imageUnavailable') }}
            </p>
            <figcaption v-if="block.caption" class="puzzle-player__caption">
              {{ block.caption }}
            </figcaption>
          </figure>

          <!-- 视频 -->
          <figure v-else-if="block.type === 'video'" class="puzzle-player__figure">
            <video class="puzzle-player__video" :src="block.url" controls preload="metadata" />
            <figcaption v-if="block.caption" class="puzzle-player__caption">
              {{ block.caption }}
            </figcaption>
          </figure>

          <!-- 富文本（内容经审核链把关） -->
          <div v-else-if="block.type === 'rich'" class="puzzle-player__rich" v-html="block.html"></div>
        </template>
      </div>

      <!-- 答题区（未解决时显示） -->
      <div v-if="!isSolved" class="puzzle-player__answer">
        <!-- 单选 -->
        <div v-if="definition.type === 'single'" class="puzzle-player__options" role="radiogroup">
          <label
            v-for="(option, index) in definition.options"
            :key="index"
            class="puzzle-player__option"
            :class="{ 'puzzle-player__option--selected': selectedIndices.includes(index) }"
          >
            <input
              class="puzzle-player__radio"
              type="radio"
              :name="`puzzle-${definition.id}`"
              :checked="selectedIndices.includes(index)"
              @change="toggleOption(index)"
            />
            <span>{{ option.text }}</span>
          </label>
        </div>

        <!-- 多选 -->
        <div v-else-if="definition.type === 'multi'" class="puzzle-player__options" role="group">
          <label
            v-for="(option, index) in definition.options"
            :key="index"
            class="puzzle-player__option"
            :class="{ 'puzzle-player__option--selected': selectedIndices.includes(index) }"
          >
            <input
              class="puzzle-player__checkbox"
              type="checkbox"
              :checked="selectedIndices.includes(index)"
              @change="toggleOption(index)"
            />
            <span>{{ option.text }}</span>
          </label>
        </div>

        <!-- 填空 -->
        <div v-else class="puzzle-player__fills">
          <input
            v-for="(_, index) in fillCount"
            :key="index"
            v-model="fillValues[index]"
            class="puzzle-player__input"
            type="text"
            :aria-label="`${t('puzzles.fillLabel')} ${index + 1}`"
            @keydown.enter="handleSubmit"
          />
        </div>

        <div class="puzzle-player__actions">
          <button class="puzzle-player__btn" type="button" @click="handleSubmit">
            {{ t('puzzles.submit') }}
          </button>
          <button
            v-if="revealedHints.length < hintList.length"
            class="puzzle-player__btn puzzle-player__btn--hint"
            type="button"
            @click="handleHint"
          >
            {{ t('puzzles.hint') }}
          </button>
        </div>

        <!-- 错误反馈 -->
        <p v-if="hasAttempted && !isSolved" class="puzzle-player__error">
          {{ t('puzzles.wrongAnswer') }}
        </p>
      </div>

      <!-- 已解决状态 -->
      <div v-if="isSolved" class="puzzle-player__solved">
        <span class="puzzle-player__solved-icon">{{ t('puzzles.solvedIcon') }}</span>
        <div>
          <p class="puzzle-player__solved-text">{{ t('puzzles.solved') }}</p>
          <p v-if="definition.explanation" class="puzzle-player__explanation">
            {{ definition.explanation }}
          </p>
        </div>
      </div>

      <!-- 已揭示的提示 -->
      <ul v-if="revealedHints.length > 0" class="puzzle-player__hints">
        <li v-for="(hint, index) in revealedHints" :key="index" class="puzzle-player__hint-item">
          {{ hint }}
        </li>
      </ul>
    </template>
  </div>
</template>

<style scoped>
.puzzle-player {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px;
  min-height: 100%;
  overflow-y: auto;
}

.puzzle-player__not-found {
  margin: 0;
  color: var(--text-secondary);
  font: 13px var(--font-ui);
}

.puzzle-player__header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.puzzle-player__eyebrow {
  margin: 0;
  color: var(--signal-red-soft);
  font: 700 10px var(--font-mono);
  text-transform: uppercase;
}

.puzzle-player__title {
  margin: 0;
  color: var(--text-primary);
  font: 600 16px var(--font-ui);
}

/* ── 题面块 ── */
.puzzle-player__blocks {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.puzzle-player__text {
  margin: 0;
  color: var(--text-secondary);
  font: 13px/1.6 var(--font-ui);
}

.puzzle-player__code {
  display: block;
  padding: 12px 16px;
  background: var(--canvas);
  border: 1px solid var(--line-default);
  color: var(--text-primary);
  font: 18px/1.4 var(--font-mono);
  letter-spacing: 2px;
  white-space: pre-wrap;
  word-break: break-all;
}

.puzzle-player__figure {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.puzzle-player__image {
  max-width: 100%;
  max-height: 240px;
  object-fit: contain;
  border: 1px solid var(--line-subtle);
  background: var(--canvas);
}

.puzzle-player__image-fallback {
  margin: 0;
  padding: 16px;
  border: 1px dashed var(--line-default);
  color: var(--text-muted);
  font: 12px var(--font-ui);
  text-align: center;
}

.puzzle-player__video {
  width: 100%;
  max-height: 240px;
  background: #000;
}

.puzzle-player__caption {
  color: var(--text-muted);
  font: 11px var(--font-ui);
}

.puzzle-player__rich {
  color: var(--text-secondary);
  font: 13px/1.6 var(--font-ui);
}

.puzzle-player__rich :deep(img) {
  max-width: 100%;
}

/* ── 答题区 ── */
.puzzle-player__answer {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.puzzle-player__options {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.puzzle-player__option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-secondary);
  font: 13px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.puzzle-player__option:hover {
  border-color: var(--signal-red-soft);
  color: var(--text-primary);
}

.puzzle-player__option--selected {
  border-color: var(--signal-red-soft);
  color: var(--text-primary);
  background: var(--surface-hover);
}

.puzzle-player__radio,
.puzzle-player__checkbox {
  accent-color: var(--signal-red-soft);
}

.puzzle-player__fills {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.puzzle-player__input {
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

.puzzle-player__input:focus {
  border-color: var(--signal-red-soft);
}

.puzzle-player__actions {
  display: flex;
  gap: 8px;
}

.puzzle-player__btn {
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

.puzzle-player__btn:hover {
  border-color: var(--signal-red-soft);
  color: var(--signal-red-soft);
}

.puzzle-player__btn--hint {
  border-style: dashed;
}

.puzzle-player__error {
  margin: 0;
  color: var(--signal-red);
  font: 12px var(--font-ui);
}

/* ── 已解决 ── */
.puzzle-player__solved {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 16px;
  background: var(--canvas);
  border: 1px solid var(--signal-mint);
  color: var(--signal-mint);
  font: 600 14px var(--font-ui);
}

.puzzle-player__solved-icon {
  font-size: 18px;
}

.puzzle-player__solved-text {
  margin: 0;
}

.puzzle-player__explanation {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font: 12px/1.6 var(--font-ui);
  font-weight: 400;
}

/* ── 提示 ── */
.puzzle-player__hints {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.puzzle-player__hint-item {
  padding: 8px 12px;
  background: var(--canvas);
  border-left: 2px solid var(--signal-red-soft);
  color: var(--text-secondary);
  font: 12px var(--font-ui);
}
</style>
