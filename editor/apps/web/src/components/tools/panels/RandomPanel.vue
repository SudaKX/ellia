<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import DropdownSelect from '../../ui/DropdownSelect.vue'
import TextField from '../../ui/TextField.vue'
import {
  base64Encode,
  randomAlphanumeric,
  randomKebabCase,
  randomSnakeCase,
  randomUuid,
  sha256Hex,
  uuidV5FromInput,
} from '../../../utils/random'

type RandomKind = 'uuid' | 'kebab' | 'snake' | 'alphanumeric'
type DerivedKind = 'sha256' | 'base64' | 'uuid'

const randomKind = ref<RandomKind>('uuid')
const segmentCount = ref('3')
const segmentLength = ref('4')
const alphaLength = ref('16')
const sourceText = ref('')
const output = ref('')
const busy = ref(false)
const error = ref<string | null>(null)
const copied = ref(false)
let copyTimer: ReturnType<typeof setTimeout> | null = null

const randomOptions = computed(() => [
  { label: 'UUID v4', value: 'uuid' },
  { label: 'kebab-case', value: 'kebab' },
  { label: 'snake_case', value: 'snake' },
  { label: '随机字母数字 [a-zA-Z0-9]', value: 'alphanumeric' },
])

const isDelimited = computed(() => randomKind.value === 'kebab' || randomKind.value === 'snake')
const isAlphanumeric = computed(() => randomKind.value === 'alphanumeric')

function generateRandom(): void {
  error.value = null
  copied.value = false
  switch (randomKind.value) {
    case 'uuid':
      output.value = randomUuid()
      break
    case 'kebab':
      output.value = randomKebabCase(Number(segmentCount.value), Number(segmentLength.value))
      break
    case 'snake':
      output.value = randomSnakeCase(Number(segmentCount.value), Number(segmentLength.value))
      break
    case 'alphanumeric':
      output.value = randomAlphanumeric(Number(alphaLength.value))
      break
  }
}

async function derive(kind: DerivedKind): Promise<void> {
  error.value = null
  copied.value = false
  if (!sourceText.value) {
    error.value = '请先输入原始数据'
    return
  }
  busy.value = true
  try {
    if (kind === 'sha256') {
      output.value = await sha256Hex(sourceText.value)
    } else if (kind === 'base64') {
      output.value = base64Encode(sourceText.value)
    } else {
      output.value = await uuidV5FromInput(sourceText.value)
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '生成失败'
  } finally {
    busy.value = false
  }
}

async function copyOutput(): Promise<void> {
  if (!output.value) return
  error.value = null
  try {
    await navigator.clipboard.writeText(output.value)
    copied.value = true
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    error.value = '复制失败'
  }
}

onBeforeUnmount(() => {
  if (copyTimer) clearTimeout(copyTimer)
})
</script>

<template>
  <div class="random-panel">
    <header class="random-panel__header">
      <h3>随机生成</h3>
    </header>

    <section class="random-panel__section">
      <h4 class="random-panel__section-title">纯随机</h4>

      <label class="random-panel__field">
        <span>类型</span>
        <DropdownSelect
          :options="randomOptions"
          :model-value="randomKind"
          @update:model-value="(value) => randomKind = value as RandomKind"
        />
      </label>

      <div v-if="isDelimited" class="random-panel__row">
        <label class="random-panel__field">
          <span>段数</span>
          <TextField v-model="segmentCount" type="number" min="1" />
        </label>
        <label class="random-panel__field">
          <span>每段长度</span>
          <TextField v-model="segmentLength" type="number" min="1" />
        </label>
      </div>

      <label v-if="isAlphanumeric" class="random-panel__field">
        <span>长度</span>
        <TextField v-model="alphaLength" type="number" min="1" />
      </label>

      <button class="btn btn--primary" type="button" @click="generateRandom">
        生成
      </button>
    </section>

    <section class="random-panel__section">
      <h4 class="random-panel__section-title">基于原数据</h4>

      <label class="random-panel__field">
        <span>原始数据</span>
        <textarea
          v-model="sourceText"
          class="random-panel__textarea"
          rows="4"
          placeholder="输入原始数据"
          spellcheck="false"
        />
      </label>

      <div class="random-panel__actions">
        <button class="btn btn--tonal" type="button" :disabled="busy" @click="derive('sha256')">
          SHA-256
        </button>
        <button class="btn btn--tonal" type="button" :disabled="busy" @click="derive('base64')">
          Base64
        </button>
        <button class="btn btn--tonal" type="button" :disabled="busy" @click="derive('uuid')">
          UUID v5
        </button>
      </div>
    </section>

    <section class="random-panel__section random-panel__output">
      <div class="random-panel__output-header">
        <h4 class="random-panel__section-title">结果</h4>
        <button
          class="btn btn--tonal btn--small"
          type="button"
          :disabled="!output"
          @click="copyOutput"
        >
          {{ copied ? '已复制' : '复制' }}
        </button>
      </div>
      <textarea
        class="random-panel__textarea random-panel__textarea--result"
        :value="output"
        rows="5"
        readonly
        placeholder="生成结果会显示在这里"
        spellcheck="false"
      />
    </section>

    <p v-if="error" class="error-text" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.random-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 10px;
  gap: 10px;
  overflow-y: auto;
}

.random-panel__header h3 {
  margin: 0;
  font-size: 1rem;
}

.random-panel__section {
  display: grid;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
}

.random-panel__section-title {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.random-panel__field {
  display: grid;
  gap: 4px;
  font-size: 0.8rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.random-panel__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.random-panel__textarea {
  width: 100%;
  padding: 6px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 6px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  color: var(--md-sys-color-on-surface, #1d1b20);
  font: inherit;
  font-size: 0.8rem;
  resize: vertical;
}

.random-panel__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.random-panel__output {
  min-height: 0;
}

.random-panel__output-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.random-panel__textarea--result {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  resize: none;
}
</style>
