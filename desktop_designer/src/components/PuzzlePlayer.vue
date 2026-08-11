<script setup lang="ts">
/**
 * # PuzzlePlayer.vue — 题目预览组件（出题器版）
 *
 * 与 desktop/src/components/puzzles/PuzzlePlayer.vue 同步维护的副本，差异：
 * - 题目定义通过 props 直接传入（而非按 id 查题库）
 * - 不持久化 solved 状态（出题器测试场景每次刷新重来）
 * - UI 文案内联中文（出题器面向中文出题者，不引入 vue-i18n）
 *
 * 渲染任意 PuzzleDefinition：富媒体题面 + 单选/多选/填空 + 提交校验 +
 * 逐条提示 + 答后解析。校验逻辑见 composables/usePuzzlePlayer.ts。
 */

import { computed, ref } from 'vue'
import { checkPuzzleAnswer } from '@/composables/usePuzzlePlayer'
import type { ContentBlock, PuzzleDefinition } from '@/types/puzzle'

const props = defineProps<{
  /** 题目定义（测试预览 / 审核预览传入） */
  definition: PuzzleDefinition
  /** 是否显示"出题者视角"（高亮正确答案，测试用） */
  revealAnswer?: boolean
}>()

// ─── 渲染辅助 ──────────────────────────────────────

/** 文本块内容 */
function blockText(block: Extract<ContentBlock, { type: 'text' }>): string {
  return block.text
}

// ─── 答题状态 ──────────────────────────────────────

/** 是否已答对 */
const isSolved = ref(false)
/** 已选项下标 */
const selectedIndices = ref<number[]>([])
/** 填空输入值 */
const fillValues = ref<string[]>([])
/** 是否提交过 */
const hasAttempted = ref(false)
/** 已揭示的提示 */
const revealedHints = ref<string[]>([])
/** 加载失败的图片 */
const failedImages = ref<Set<string>>(new Set())

/** 填空输入框数量 */
const fillCount = computed(() => props.definition.fillAnswers?.length ?? 1)

/** 切换选项（单选替换 / 多选切换） */
function toggleOption(index: number) {
  const definition = props.definition
  if (definition.type === 'single') {
    selectedIndices.value = [index]
    return
  }
  const current = selectedIndices.value
  selectedIndices.value = current.includes(index)
    ? current.filter((i) => i !== index)
    : [...current, index]
}

/** 提交校验 */
function handleSubmit() {
  const correct = checkPuzzleAnswer(
    props.definition,
    selectedIndices.value,
    fillValues.value,
  )
  if (correct) {
    isSolved.value = true
    return
  }
  hasAttempted.value = true
}

/** 揭示下一条提示 */
function handleHint() {
  const all = props.definition.hints ?? []
  if (revealedHints.value.length >= all.length) return
  revealedHints.value.push(all[revealedHints.value.length])
}

/** 图片加载失败占位 */
function handleImageError(url: string) {
  failedImages.value = new Set(failedImages.value).add(url)
}

/** 正确答案下标（出题者视角） */
const correctIndices = computed(() =>
  (props.definition.options ?? [])
    .map((option, index) => (option.correct ? index : -1))
    .filter((index) => index !== -1),
)
</script>

<template>
  <div class="puzzle-player">
    <header class="puzzle-player__header">
      <p class="puzzle-player__eyebrow">谜题预览</p>
      <h2 class="puzzle-player__title">{{ definition.title }}</h2>
    </header>

    <!-- 题面（富媒体块） -->
    <div class="puzzle-player__blocks">
      <template v-for="(block, i) in definition.blocks" :key="i">
        <p v-if="block.type === 'text' && block.variant !== 'code'" class="puzzle-player__text">
          {{ blockText(block) }}
        </p>
        <code v-else-if="block.type === 'text'" class="puzzle-player__code">
          {{ blockText(block) }}
        </code>

        <figure v-else-if="block.type === 'image'" class="puzzle-player__figure">
          <img
            v-if="!failedImages.has(block.url)"
            class="puzzle-player__image"
            :src="block.url"
            :alt="block.alt ?? block.caption ?? definition.title"
            loading="lazy"
            @error="handleImageError(block.url)"
          />
          <p v-else class="puzzle-player__image-fallback">图片加载失败</p>
          <figcaption v-if="block.caption" class="puzzle-player__caption">
            {{ block.caption }}
          </figcaption>
        </figure>

        <figure v-else-if="block.type === 'video'" class="puzzle-player__figure">
          <video class="puzzle-player__video" :src="block.url" controls preload="metadata" />
          <figcaption v-if="block.caption" class="puzzle-player__caption">
            {{ block.caption }}
          </figcaption>
        </figure>

        <div v-else-if="block.type === 'rich'" class="puzzle-player__rich" v-html="block.html"></div>
      </template>
    </div>

    <!-- 答题区（未答对时显示） -->
    <div v-if="!isSolved" class="puzzle-player__answer">
      <!-- 单选 -->
      <div v-if="definition.type === 'single'" class="puzzle-player__options" role="radiogroup">
        <label
          v-for="(option, index) in definition.options"
          :key="index"
          class="puzzle-player__option"
          :class="{
            'puzzle-player__option--selected': selectedIndices.includes(index),
            'puzzle-player__option--correct': revealAnswer && correctIndices.includes(index),
          }"
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
          :class="{
            'puzzle-player__option--selected': selectedIndices.includes(index),
            'puzzle-player__option--correct': revealAnswer && correctIndices.includes(index),
          }"
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
          :aria-label="`填空 ${index + 1}`"
          @keydown.enter="handleSubmit"
        />
      </div>

      <div class="puzzle-player__actions">
        <button class="puzzle-player__btn" type="button" @click="handleSubmit">提交</button>
        <button
          v-if="revealedHints.length < (definition.hints?.length ?? 0)"
          class="puzzle-player__btn puzzle-player__btn--hint"
          type="button"
          @click="handleHint"
        >
          提示
        </button>
      </div>

      <p v-if="hasAttempted && !isSolved" class="puzzle-player__error">答案不正确，请重试。</p>
    </div>

    <!-- 已答对 -->
    <div v-if="isSolved" class="puzzle-player__solved">
      <span class="puzzle-player__solved-icon">✓</span>
      <div>
        <p class="puzzle-player__solved-text">回答正确！</p>
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
  </div>
</template>

<style scoped>
.puzzle-player {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 100%;
  overflow-y: auto;
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

.puzzle-player__option--correct {
  border-color: var(--signal-mint);
  color: var(--signal-mint);
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

/* ── 已答对 ── */
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
