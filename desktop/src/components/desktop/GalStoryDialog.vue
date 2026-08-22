<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import type { StoryChoice, StoryNode, StoryStageCharacter } from '@/composables/useStoryDialog'
import { MAX_CHOICES } from '@/composables/useStoryDialog'
import { useAudioService } from '@/composables/useAudioService'

const props = defineProps<{
  nodes: StoryNode[]
  charDelay?: number
  autoDelay?: number
}>()

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n({ useScope: 'global' })
const audio = useAudioService()
const index = ref(0)
const typedText = ref('')
const isTyping = ref(false)
const sliderValue = ref(0)
const autoSpeed = ref<1 | 2 | 5 | null>(null)
const textRef = ref<HTMLElement | null>(null)
const stageRef = ref<HTMLElement | null>(null)
const dialogueRef = ref<HTMLElement | null>(null)
const current = computed(() => props.nodes[index.value] ?? null)
const stageCharacters = ref<StoryStageCharacter[]>([])
const portraitBottoms = ref<Record<string, number>>({})

let typeTimer: ReturnType<typeof setInterval> | null = null
let autoTimer: ReturnType<typeof setTimeout> | null = null
let stopAudio: (() => void) | null = null
let resizeObserver: ResizeObserver | null = null

function clearPlaybackTimers() {
  if (typeTimer) clearInterval(typeTimer)
  if (autoTimer) clearTimeout(autoTimer)
  typeTimer = null
  autoTimer = null
  isTyping.value = false
}

async function scrollToBottom() {
  await nextTick()
  if (textRef.value) textRef.value.scrollTop = textRef.value.scrollHeight
}

function scheduleAutoAdvance() {
  const node = current.value
  if (!node || !autoSpeed.value || node.choices || node.slider) return
  autoTimer = setTimeout(() => goto(node.next), Math.max(160, (props.autoDelay ?? 1100) / autoSpeed.value))
}

function startTyping() {
  const node = current.value
  if (!node?.text) {
    typedText.value = ''
    scheduleAutoAdvance()
    return
  }

  typedText.value = ''
  let cursor = 0
  isTyping.value = true
  const speed = autoSpeed.value ?? 1
  const delay = Math.max(5, (props.charDelay ?? 30) / speed)
  typeTimer = setInterval(() => {
    cursor += 1
    typedText.value = node.text!.slice(0, cursor)
    void scrollToBottom()
    if (cursor >= node.text!.length) {
      if (typeTimer) clearInterval(typeTimer)
      typeTimer = null
      isTyping.value = false
      scheduleAutoAdvance()
    }
  }, delay)
}

function handleNodeEnter() {
  clearPlaybackTimers()
  stopAudio?.()
  stopAudio = null
  const node = current.value
  if (!node) return
  if (node.stageCharacters) stageCharacters.value = node.stageCharacters
  if (node.slider) sliderValue.value = node.slider.initial ?? Math.round((node.slider.min + node.slider.max) / 2)
  node.effect?.()
  if (node.audio) stopAudio = audio.playParallelFile(node.audio)
  startTyping()
}

function goto(targetId?: string) {
  if (targetId !== undefined) {
    const target = props.nodes.findIndex((node) => node.id === targetId)
    if (target !== -1) {
      index.value = target
      return
    }
  }
  if (index.value < props.nodes.length - 1) index.value += 1
  else emit('close')
}

function handleAdvance() {
  const node = current.value
  if (!node) return
  if (isTyping.value) {
    clearPlaybackTimers()
    typedText.value = node.text ?? ''
    scheduleAutoAdvance()
    return
  }
  if (!node.choices && !node.slider) goto(node.next)
}

function handleChoice(choice: StoryChoice) {
  choice.effect?.()
  goto(choice.next)
}

function handleSliderSubmit() {
  const slider = current.value?.slider
  if (!slider) return
  slider.effect?.(sliderValue.value)
  goto(slider.next(sliderValue.value))
}

function cycleAutoSpeed() {
  const speeds: (1 | 2 | 5 | null)[] = [null, 1, 2, 5]
  autoSpeed.value = speeds[(speeds.indexOf(autoSpeed.value) + 1) % speeds.length]
  if (!isTyping.value) {
    if (autoTimer) clearTimeout(autoTimer)
    scheduleAutoAdvance()
  }
}

function updatePortraitPosition(character: StoryStageCharacter, image: HTMLImageElement) {
  const stage = stageRef.value
  const dialogue = dialogueRef.value
  if (!stage || !dialogue || !image.naturalWidth) return
  const renderedHeight = image.naturalHeight * (image.clientWidth / image.naturalWidth)
  const dialogueTopFromBottom = stage.clientHeight - dialogue.offsetTop
  // 顶部对齐模式：图片顶部相对窗口顶部的偏移为 anchorTop × 图片高度
  // （0 = 贴窗口顶；正数 = 顶部超出窗口被遮住；负数 = 顶部留空）
  const bottom = character.anchorTop !== undefined
    ? stage.clientHeight - renderedHeight * (1 - (character.anchorTop ?? 0))
    : dialogueTopFromBottom - renderedHeight * (1 - (character.anchorY ?? 1))
  portraitBottoms.value = {
    ...portraitBottoms.value,
    [character.id]: bottom,
  }
}

function handlePortraitLoad(character: StoryStageCharacter, event: Event) {
  if (event.currentTarget instanceof HTMLImageElement) updatePortraitPosition(character, event.currentTarget)
}

function updateAllPortraitPositions() {
  for (const character of stageCharacters.value) {
    const image = stageRef.value?.querySelector<HTMLImageElement>(`[data-stage-character="${character.id}"]`)
    if (image?.complete) updatePortraitPosition(character, image)
  }
}

watch(index, handleNodeEnter, { immediate: true })
onMounted(() => {
  resizeObserver = new ResizeObserver(() => updateAllPortraitPositions())
  if (stageRef.value) resizeObserver.observe(stageRef.value)
  if (dialogueRef.value) resizeObserver.observe(dialogueRef.value)
})
onBeforeUnmount(() => {
  clearPlaybackTimers()
  stopAudio?.()
  resizeObserver?.disconnect()
})
</script>

<template>
  <div class="gal-story" @click="handleAdvance">
    <div ref="stageRef" class="gal-story__stage">
      <TransitionGroup name="gal-story-image">
        <div
          v-for="character in stageCharacters"
          :key="character.id"
          :class="[
            'gal-story__portrait',
            `gal-story__portrait--${character.position}`,
            { 'gal-story__portrait--hologram': character.effect === 'hologram' },
            { 'gal-story__portrait--dimmed': !character.speakerNames.includes(current?.speaker ?? '') },
          ]"
          :style="{
            bottom: `${portraitBottoms[character.id] ?? 0}px`,
            width: `${(character.scale ?? 1) * 32}%`,
          }"
        >
          <img
            :src="character.image"
            :class="[
              'gal-story__image',
            `gal-story__image--${character.position}`,
            `gal-story__image--${character.animation ?? 'fade'}`,
          ]"
          alt=""
          :data-stage-character="character.id"
          @load="handlePortraitLoad(character, $event)"
          />
          <div
            v-if="character.effect === 'hologram'"
            class="gal-story__hologram-overlay"
            :style="{ maskImage: `url(${character.image})`, WebkitMaskImage: `url(${character.image})` }"
          ></div>
        </div>
      </TransitionGroup>
    </div>

    <section ref="dialogueRef" class="gal-story__dialogue" @click.stop="handleAdvance">
      <div class="gal-story__controls" @click.stop>
        <button
          :class="['gal-story__auto-button', { 'gal-story__auto-button--active': autoSpeed }]"
          type="button"
          @click="cycleAutoSpeed"
        >
          {{ autoSpeed ? `${t('story.dialog.auto')} ${autoSpeed}X` : t('story.dialog.auto') }}
        </button>
      </div>
      <div v-if="current?.speaker" class="gal-story__speaker">{{ current.speaker }}</div>
      <p v-if="current?.text" ref="textRef" class="gal-story__text">
        {{ typedText }}<span v-if="isTyping" class="gal-story__cursor">_</span>
      </p>
      <div v-if="current?.choices" class="gal-story__choices" @click.stop>
        <button
          v-for="(choice, choiceIndex) in current.choices.slice(0, MAX_CHOICES)"
          :key="choiceIndex"
          class="gal-story__choice"
          type="button"
          @click="handleChoice(choice)"
        >
          {{ choice.label }}
        </button>
      </div>
      <div v-else-if="current?.slider" class="gal-story__slider" @click.stop>
        <span>{{ current.slider.label }}</span>
        <input v-model.number="sliderValue" type="range" :min="current.slider.min" :max="current.slider.max" :step="current.slider.step ?? 1" />
        <span>{{ sliderValue }}</span>
        <button class="gal-story__choice" type="button" @click="handleSliderSubmit">{{ current.slider.submitLabel ?? t('story.dialog.submit') }}</button>
      </div>
      <span v-else-if="!isTyping" class="gal-story__next">▼</span>
    </section>
  </div>
</template>

<style scoped>
.gal-story { position: relative; height: 100%; overflow: hidden; background: var(--canvas); color: var(--text-primary); }
.gal-story__stage { position: absolute; inset: 0; overflow: hidden; background: linear-gradient(180deg, var(--surface-raised), var(--canvas)); }
.gal-story__stage::after { position: absolute; inset: 0; background: linear-gradient(180deg, transparent 38%, color-mix(in srgb, var(--canvas) 74%, transparent)); content: ''; pointer-events: none; }
.gal-story__portrait { position: absolute; width: 32%; filter: drop-shadow(0 18px 20px color-mix(in srgb, var(--canvas) 70%, transparent)); transition: filter .2s ease; }
.gal-story__portrait--left { left: 4%; }
.gal-story__portrait--center { left: 29%; }
.gal-story__portrait--right { right: 4%; }
.gal-story__image { display: block; width: 100%; height: auto; }
.gal-story__image--left, .gal-story__image--center, .gal-story__image--right { position: static; }
.gal-story__image--slide-left { animation: slide-left 0.42s ease-out both; }
.gal-story__image--slide-right { animation: slide-right 0.42s ease-out both; }
.gal-story__image--rise { animation: rise 0.42s ease-out both; }
.gal-story__image--fade { animation: fade 0.32s ease-out both; }
.gal-story__image--none { animation: none; }
.gal-story__portrait--dimmed { filter: brightness(.42) saturate(.7) drop-shadow(0 18px 20px color-mix(in srgb, var(--canvas) 70%, transparent)); }
.gal-story__portrait--hologram { isolation: isolate; opacity: .72; filter: hue-rotate(154deg) saturate(1.6) brightness(1.3) blur(.4px) drop-shadow(4px 0 1px color-mix(in srgb, var(--signal-mint) 80%, transparent)) drop-shadow(-4px 0 1px color-mix(in srgb, var(--signal-red-soft) 65%, transparent)) drop-shadow(0 0 12px color-mix(in srgb, var(--signal-mint) 40%, transparent)); animation: hologram-flicker 1.2s steps(2) infinite, hologram-breathe 3.6s ease-in-out infinite; }
.gal-story__hologram-overlay { position: absolute; inset: 0; z-index: 1; pointer-events: none; mask-size: 100% auto; mask-position: top center; mask-repeat: no-repeat; -webkit-mask-size: 100% auto; -webkit-mask-position: top center; -webkit-mask-repeat: no-repeat; background: repeating-linear-gradient(0deg, color-mix(in srgb, var(--signal-red-soft) 28%, transparent) 0 1px, transparent 1px 3px); mix-blend-mode: screen; animation: hologram-scan 0.8s linear infinite; }
.gal-story__dialogue { position: absolute; right: 0; bottom: 0; left: 0; min-height: 38%; padding: 38px 28px 24px; border-top: 1px solid color-mix(in srgb, var(--signal-red-border) 68%, var(--line-default)); background: color-mix(in srgb, var(--surface-raised) 82%, transparent); backdrop-filter: blur(8px); cursor: pointer; }
.gal-story__speaker { position: absolute; top: -18px; left: 26px; padding: 7px 18px; border: 1px solid var(--signal-red-border); background: var(--surface-panel); color: var(--signal-red); font: 700 14px var(--font-ui); }
.gal-story__text { max-height: 132px; margin: 0; overflow-y: auto; font: 17px/1.8 var(--font-ui); white-space: pre-wrap; word-break: break-word; }
.gal-story__controls { position: absolute; top: 10px; right: 16px; display: flex; gap: 6px; }
.gal-story__auto-button, .gal-story__choice { border: 1px solid var(--line-default); border-radius: 0; color: var(--text-secondary); background: color-mix(in srgb, var(--surface-panel) 90%, transparent); font: 11px var(--font-mono); }
.gal-story__auto-button { padding: 5px 7px; }
.gal-story__auto-button--active, .gal-story__auto-button:hover, .gal-story__choice:hover { border-color: var(--signal-red); color: var(--text-primary); background: var(--surface-hover); }
.gal-story__choices { display: grid; gap: 8px; margin-top: 16px; }
.gal-story__choice { min-height: 34px; padding: 8px 14px; text-align: left; }
.gal-story__slider { display: flex; align-items: center; gap: 10px; margin-top: 14px; color: var(--text-secondary); font: 12px var(--font-mono); }
.gal-story__slider input { flex: 1; accent-color: var(--signal-red); }
.gal-story__next { position: absolute; right: 24px; bottom: 14px; color: var(--signal-red-soft); animation: next 0.8s steps(1) infinite; }
.gal-story__cursor { color: var(--signal-red-soft); animation: next 0.8s steps(1) infinite; }
.gal-story-image-enter-active, .gal-story-image-leave-active { transition: opacity 0.24s ease; }
.gal-story-image-enter-from, .gal-story-image-leave-to { opacity: 0; }
@keyframes fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes rise { from { opacity: 0; transform: translateY(28px); } to { opacity: 1; transform: translateY(0); } }
@keyframes slide-left { from { opacity: 0; transform: translateX(36px); } to { opacity: 1; transform: translateX(0); } }
@keyframes slide-right { from { opacity: 0; transform: translateX(-36px); } to { opacity: 1; transform: translateX(0); } }
@keyframes next { 0%, 49% { opacity: 1; } 50%, 100% { opacity: .25; } }
@keyframes hologram-flicker { 0%, 78% { opacity: .72; transform: translateX(0); } 79% { opacity: .35; transform: translateX(-4px) scaleX(1.02); } 82% { opacity: .8; transform: translateX(3px) scaleX(.98); } 85% { opacity: .55; transform: translateX(-1px); } 88%, 100% { opacity: .72; transform: translateX(0); } }
@keyframes hologram-breathe { 0%, 100% { opacity: .72; } 50% { opacity: .55; } }
@keyframes hologram-scan { from { background-position: 0 0; } to { background-position: 0 12px; } }

</style>
