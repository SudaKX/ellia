<script setup lang="ts">
/**
 * # TextEditor.vue — 文本阅读器 / 编辑器（FakeOS 记事本）
 *
 * 模仿 Windows 11 记事本的文件查看与编辑应用。
 * 由 FileExplorer 双击 `.txt` / `.log` 文件时打开，一个文件一个独立窗口。
 *
 * ## 功能
 *
 * - **阅读 / 编辑**：默认进入编辑（读写）模式，可一键切换为只读的阅读模式
 * - **保存**：点击"保存"或关闭时选择保存 → 弹出权限不足窗口
 *   （与网络设置"编辑 IP/DNS"被拒的弹窗完全一致：MessageBox + PermissionDenied 模态）
 * - **字号调节**：工具栏 A- / A+ 按钮，范围 10px ~ 24px
 * - **关闭保护**：有未保存修改时点标题栏 X → 弹出"是否保存更改？"提示，
 *   选择"保存"→ 权限不足弹窗（无法真正写入文件系统，保持静态 mock 不变）；
 *   选择"不保存"→ 直接关闭；选择"取消"→ 保持打开
 *
 * ## 为什么保存永远失败
 *
 * useFileSystem 的文件树是模块级静态常量，设计上不可变。
 * 保存被权限弹窗拦截正是叙事需要（玩家账户无权修改系统文件），
 * 因此本组件不做任何写回操作，也无需改动文件系统层。
 *
 * ## 关闭拦截的架构
 *
 * 标题栏 X 由 DesktopView 的 `closeAction` 接管（见 useWindowService 的 dockable 窗口）。
 * 本组件挂载时向 useTextEditorSession 注册会话（含 `requestClose` 回调），
 * DesktopView 的 closeAction → requestTextEditorClose(windowId) → 本组件自行分支。
 * 未修改时直接 `emit('close')` 走 WindowFrame 标准关闭动画。
 *
 * ## 与 darksky 分支区别
 *
 * darksky 分支无此应用（其文件浏览器双击仅预览）。
 * 本组件依赖本分支保留的模态窗口 + MessageBox + PermissionDenied 能力。
 *
 * ## @example
 *
 * ```ts
 * // FileExplorer 双击文件时创建窗口
 * const result = windowService.send({
 *   type: 'create-window',
 *   payload: {
 *     titleKey: 'textEditor.title',
 *     title: file.name,
 *     icon: FileText,
 *     component: TextEditor,
 *     componentProps: { fileName: file.name, fileContent: file.content ?? '' },
 *     dockable: true,
 *     dockTitle: file.name,
 *     ...
 *   },
 * })
 * result.componentProps = { ...result.componentProps, windowId: result.id }
 * ```
 */

import { computed, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { Eye, FileText, Minus, Pencil, Plus, Save } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

import MessageBox from '@/components/desktop/MessageBox.vue'
import PermissionDenied from '@/components/desktop/PermissionDenied.vue'
import { useAudioService } from '@/composables/useAudioService'
import {
  registerTextEditorSession,
  unregisterTextEditorSession,
} from '@/composables/useTextEditorSession'
import type { WindowService } from '@/composables/useWindowService'

const props = defineProps<{
  /** 打开的文件名（窗口标题 / Dock 条目名 / 提示文案共用） */
  fileName: string
  /** 文件初始内容 */
  fileContent: string
  /** 所属窗口 ID（FileExplorer 创建窗口后回填，用于会话注册） */
  windowId: string
}>()

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n({ useScope: 'global' })
const windowService = inject<WindowService>('windowService')
const audioService = useAudioService()

// ─── 编辑器状态 ──────────────────────────────────────

/** 打开时的原始内容（保存基准，未修改比较目标） */
const originalContent = ref(props.fileContent ?? '')
/** 当前编辑内容 */
const content = ref(props.fileContent ?? '')
/** 是否有未保存的修改 */
const isModified = computed(() => content.value !== originalContent.value)
/** 当前模式：edit（默认读写）| read（只读阅读） */
const mode = ref<'edit' | 'read'>('edit')
/** 正文字号（px），范围 10 ~ 24 */
const fontSize = ref(14)
/** 关闭时的保存确认层是否显示 */
const showSavePrompt = ref(false)

// ─── 会话注册（供 DesktopView closeAction 委托） ────

/**
 * 关闭请求回调：有未保存修改 → 弹保存确认；否则直接走标准关闭流程。
 * 通过 emit('close') 通知 WindowFrame 播放关闭动画后真正销毁窗口。
 */
function requestClose() {
  if (isModified.value) {
    showSavePrompt.value = true
  } else {
    emit('close')
  }
}

onMounted(() => {
  registerTextEditorSession(props.windowId, {
    get modified() {
      return isModified.value
    },
    requestClose,
  })
})

onBeforeUnmount(() => {
  unregisterTextEditorSession(props.windowId)
})

// ─── 保存与权限不足弹窗 ──────────────────────────────

/**
 * 弹出权限不足模态窗口（与网络设置"编辑 IP/DNS"被拒一致）。
 * 保存请求一律被拒绝——玩家无权修改系统文件。
 */
function openPermissionDenied() {
  audioService.play('system-alert')
  windowService?.send({
    type: 'create-window',
    payload: {
      titleKey: 'textEditor.permissionTitle',
      icon: FileText,
      component: MessageBox,
      componentProps: { contentComponent: PermissionDenied },
      defaultWidth: 440,
      defaultHeight: 220,
      placement: 'center',
      mode: 'modal',
      resizable: false,
      filters: { glitch: true },
      controls: { minimize: false, close: true },
    },
  })
}

/** 工具栏"保存"按钮：直接触发权限不足弹窗 */
function handleSave() {
  openPermissionDenied()
}

// ─── 保存确认层动作 ──────────────────────────────────

/** 保存确认 → 保存：弹权限不足（保存永远失败） */
function handleSavePromptSave() {
  showSavePrompt.value = false
  openPermissionDenied()
}

/** 保存确认 → 不保存：直接关闭窗口 */
function handleSavePromptDiscard() {
  showSavePrompt.value = false
  emit('close')
}

/** 保存确认 → 取消：回到编辑，什么都不做 */
function handleSavePromptCancel() {
  showSavePrompt.value = false
}

/** 调节字号，钳制在 [10, 24] */
function changeFontSize(delta: number) {
  fontSize.value = Math.min(24, Math.max(10, fontSize.value + delta))
}
</script>

<template>
  <div class="text-editor">
    <!-- 工具栏：保存 / 模式切换 / 字号调节 / 修改指示 -->
    <header class="text-editor__toolbar">
      <button
        class="text-editor__btn"
        type="button"
        :title="t('textEditor.save')"
        @click="handleSave"
      >
        <Save :size="14" :stroke-width="1.8" />
        <span>{{ t('textEditor.save') }}</span>
      </button>

      <button
        class="text-editor__btn"
        type="button"
        :title="mode === 'edit' ? t('textEditor.readMode') : t('textEditor.editMode')"
        @click="mode = mode === 'edit' ? 'read' : 'edit'"
      >
        <Eye v-if="mode === 'edit'" :size="14" :stroke-width="1.8" />
        <Pencil v-else :size="14" :stroke-width="1.8" />
        <span>{{ mode === 'edit' ? t('textEditor.readMode') : t('textEditor.editMode') }}</span>
      </button>

      <span class="text-editor__spacer" aria-hidden="true"></span>

      <span class="text-editor__font">
        <button
          class="text-editor__btn"
          type="button"
          :title="t('textEditor.decreaseFont')"
          :disabled="fontSize <= 10"
          @click="changeFontSize(-1)"
        >
          <Minus :size="14" :stroke-width="1.8" />
        </button>
        <span class="text-editor__font-size" aria-label="font size">{{ fontSize }}px</span>
        <button
          class="text-editor__btn"
          type="button"
          :title="t('textEditor.increaseFont')"
          :disabled="fontSize >= 24"
          @click="changeFontSize(1)"
        >
          <Plus :size="14" :stroke-width="1.8" />
        </button>
      </span>

      <span
        v-if="isModified"
        class="text-editor__modified"
        :title="t('textEditor.modified')"
        aria-label="modified"
      >*</span>
    </header>

    <!-- 正文：编辑模式可写，阅读模式只读 -->
    <textarea
      class="text-editor__textarea"
      :value="content"
      :readonly="mode === 'read'"
      :style="{ fontSize: fontSize + 'px' }"
      :aria-label="t('textEditor.editArea')"
      :spellcheck="false"
      @input="content = ($event.target as HTMLTextAreaElement).value"
    ></textarea>

    <!-- 关闭保存确认层 -->
    <Transition name="save-prompt">
      <div
        v-if="showSavePrompt"
        class="text-editor__prompt"
        role="dialog"
        aria-modal="true"
        aria-labelledby="save-prompt-title"
      >
        <div class="text-editor__prompt-card">
          <p id="save-prompt-title" class="text-editor__prompt-title">
            {{ t('textEditor.savePromptTitle') }}
          </p>
          <p class="text-editor__prompt-message">
            {{ t('textEditor.savePromptMessage', { name: props.fileName }) }}
          </p>
          <div class="text-editor__prompt-actions">
            <button class="text-editor__prompt-btn" type="button" @click="handleSavePromptSave">
              {{ t('textEditor.savePromptSave') }}
            </button>
            <button class="text-editor__prompt-btn" type="button" @click="handleSavePromptDiscard">
              {{ t('textEditor.savePromptDiscard') }}
            </button>
            <button
              class="text-editor__prompt-btn text-editor__prompt-btn--cancel"
              type="button"
              @click="handleSavePromptCancel"
            >
              {{ t('textEditor.savePromptCancel') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.text-editor {
  position: relative;
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  background: var(--canvas);
}

/* ── 工具栏 ── */
.text-editor__toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  padding: 6px 8px;
  border-bottom: 1px solid var(--line-subtle);
  background: var(--surface-panel);
}

.text-editor__btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 26px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 0;
  color: var(--text-secondary);
  background: transparent;
  font: 600 11px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.text-editor__btn:hover:not(:disabled) {
  border-color: var(--line-default);
  color: var(--text-primary);
  background: var(--surface-hover);
}

.text-editor__btn:disabled {
  color: var(--text-muted);
  opacity: 0.4;
  cursor: default;
}

.text-editor__spacer {
  flex: 1;
}

.text-editor__font {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.text-editor__font-size {
  min-width: 34px;
  color: var(--text-muted);
  font: 11px var(--font-mono);
  text-align: center;
}

.text-editor__modified {
  color: var(--signal-red-soft);
  font: 700 14px var(--font-mono);
  line-height: 1;
  padding: 0 2px;
}

/* ── 正文 ── */
.text-editor__textarea {
  flex: 1;
  min-height: 0;
  width: 100%;
  padding: 12px;
  border: none;
  outline: none;
  resize: none;
  color: var(--text-primary);
  background: var(--canvas);
  font-family: var(--font-mono);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

.text-editor__textarea[readonly] {
  color: var(--text-secondary);
}

/* ── 保存确认层 ── */
.text-editor__prompt {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: grid;
  place-items: center;
  background: rgb(0 0 0 / 54%);
}

.text-editor__prompt-card {
  width: min(320px, calc(100% - 32px));
  border: 1px solid var(--line-default);
  border-radius: 0;
  background: var(--surface-raised);
  box-shadow: 0 18px 56px rgb(0 0 0 / 45%);
  padding: 20px 20px 16px;
}

.text-editor__prompt-title {
  margin: 0 0 8px;
  color: var(--text-primary);
  font: 700 14px var(--font-ui);
}

.text-editor__prompt-message {
  margin: 0 0 18px;
  color: var(--text-secondary);
  font: 12px/1.55 var(--font-ui);
  word-break: break-all;
}

.text-editor__prompt-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.text-editor__prompt-btn {
  min-width: 76px;
  min-height: 30px;
  padding: 0 12px;
  border: 1px solid var(--line-default);
  border-radius: 0;
  color: var(--text-primary);
  background: transparent;
  font: 600 11px var(--font-ui);
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s, background-color 0.12s;
}

.text-editor__prompt-btn:hover {
  border-color: var(--signal-mint);
  color: var(--signal-mint);
  background: var(--surface-hover);
}

.text-editor__prompt-btn--cancel:hover {
  border-color: var(--line-default);
  color: var(--text-secondary);
}

/* ── 确认层动画 ── */
.save-prompt-enter-active,
.save-prompt-leave-active {
  transition: opacity 0.15s ease;
}

.save-prompt-enter-from,
.save-prompt-leave-to {
  opacity: 0;
}
</style>
