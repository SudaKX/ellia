<script setup lang="ts">
/**
 * # Terminal.vue — 交互式命令终端
 *
 * FakeOS 的终端模拟器组件，提供完整的命令行交互体验。
 *
 * ## 架构设计
 *
 * ```
 * ┌─ Terminal.vue ─────────────────────────────────────┐
 * │                                                     │
 * │  输入层（隐藏 <input>）                               │
 * │    ├─ v-model ↔ input ref                          │
 * │    ├─ @keydown.Enter → executeCommand()            │
 * │    ├─ @keydown.ArrowUp/Down → navigateHistory()    │
 * │    └─ 点击终端任意位置 → focus()                     │
 * │                                                     │
 * │  渲染层（Vue 模板）                                   │
 * │    ├─ lines[] → 历史输出行                          │
 * │    ├─ prompt + input + cursor → 当前输入行          │
 * │    └─ 自动滚动到底部（nextTick + scrollTop）          │
 * │                                                     │
 * │  命令路由层                                          │
 * │    ├─ commandRegistry.get(name) → Command          │
 * │    ├─ 权限检查（requiredPrivilege vs ctx）           │
 * │    └─ execute(args, ctx) → string[]                │
 * │                                                     │
 * │  CommandContext                                     │
 * │    ├─ user: 'PLAYER' | 'JDKTrigger'                │
 * │    ├─ privilegeClass: 'LIMITED' | 'ADMIN'          │
 * │    └─ t: (key, params?) => string  (i18n)          │
 * │                                                     │
 * └─────────────────────────────────────────────────────┘
 * ```
 *
 * ## 为什么用隐藏 <input> 接收键盘而非 contenteditable
 *
 * - contenteditable 在不同浏览器上有不一致的光标行为
 * - 隐藏 input + Vue 渲染层完全控制显示，无兼容性问题
 * - input 事件天然支持 IME（中文输入法），contenteditable 需要额外处理
 *
 * ## 为什么权限检查放在 Terminal.vue 而非命令内部
 *
 * - 一致性：所有命令共享同一鉴权逻辑
 * - 安全：即使后续有人新增命令忘记了权限校验，也会被路由层拦截
 * - 可审计：只需看一处就知道权限策略
 *
 * ## 与 darksky 分支的区别
 *
 * darksky 分支无终端实现（该分支为纯前端占位），本分支完整实现了：
 * - 命令注册表机制（registries/commands.ts）
 * - 11 个命令模块（commands/*.ts）
 * - i18n 翻译集成（terminal.* 段）
 *
 * @example
 * ```ts
 * // 启动终端窗口
 * windowService.open('terminal')
 * ```
 */

import { inject, nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Puzzle } from 'lucide-vue-next'

import type { CommandContext, Privilege } from '@/registries/commands'
import { commandRegistry } from '@/registries/commands'
import { puzzleRegistry } from '@/registries/puzzles'
import { useDesktopStore } from '@/stores/desktop'
import { CLEAR_MARKER } from '@/commands/clear'
import { evaluateExpression, isMathExpression } from '@/commands/calc'
import type { WindowService } from '@/composables/useWindowService'

// 副作用导入：触发所有命令模块的 registerCommand() 调用
import '@/commands/calc'
import '@/commands/cat'
import '@/commands/cd'
import '@/commands/clear'
import '@/commands/date'
import '@/commands/echo'
import '@/commands/ellia'
import '@/commands/exit'
import '@/commands/help'
import '@/commands/ls'
import '@/commands/man'
import '@/commands/pwd'
import '@/commands/sil'
import '@/commands/sudo'
import '@/commands/uname'
import '@/commands/whoami'

// ─── i18n & Store & WindowService ────────────────────

const { t } = useI18n({ useScope: 'global' })
const desktop = useDesktopStore()

/**
 * 从 DesktopView 注入的 windowService 单例。
 * 不能用 useWindowService() 直接创建——那会生成一个新实例（独立的窗口列表），
 * 必须通过 provide/inject 获取 DesktopView 持有的同一实例。
 */
const windowService = inject<WindowService>('windowService')

// ─── 核心状态 ────────────────────────────────────────

/** 输出行历史（每条是一行渲染文本） */
const lines = ref<string[]>([])

/** 当前输入缓冲区 */
const input = ref('')

/** 已执行命令历史（不含空命令），用于 ↑↓ 键导航 */
const commandHistory = ref<string[]>([])

/**
 * 命令历史导航索引。
 * -1 = 未在历史中导航（显示当前新输入）
 * 0 = 最新一条历史
 * N = 第 N 条历史（越大约旧）
 */
const historyIndex = ref(-1)

/** 隐藏 input 的模板引用 */
const hiddenInput = ref<HTMLInputElement | null>(null)

/** 输出区域的模板引用（用于自动滚动到底部） */
const outputRef = ref<HTMLDivElement | null>(null)

/** HTML 行标记：以 \x00 开头的行表示安全的 HTML 内容 */
const HTML_MARKER = '\x00'

function isHtmlLine(line: string): boolean {
  return line.startsWith(HTML_MARKER)
}

function stripHtmlMarker(line: string): string {
  return line.slice(HTML_MARKER.length)
}

// ─── CommandContext 构建 ─────────────────────────────

/**
 * 构建当前会话的命令上下文。
 * 每次执行命令时重新构建，确保 user / privilegeClass 是最新值。
 */
function buildContext(): CommandContext {
  return {
    user: desktop.currentUser,
    privilegeClass: desktop.privilegeClass as Privilege,
    t: (key: string, params?: Record<string, string>) => t(key, params ?? {}),
    // 谜题窗口创建回调
    openPuzzleWindow: (puzzle) => {
      if (!windowService) return false
      const result = windowService.send({
        type: 'create-window',
        payload: {
          titleKey: puzzle.nameKey,
          icon: Puzzle,
          component: puzzle.component,
          componentProps: { puzzleId: puzzle.id },
          defaultWidth: puzzle.defaultWidth,
          defaultHeight: puzzle.defaultHeight,
          placement: 'center',
          resizable: puzzle.resizable ?? true,
        },
      })
      return result !== undefined && result !== null
    },
    // 关闭当前终端窗口
    closeTerminal: () => {
      if (!windowService) return
      const termWin = windowService.windows.value.find(
        (w) => w.applicationId === 'terminal' && !w.isMinimized,
      )
      if (termWin) {
        windowService.send({ type: 'minimize-window', windowId: termWin.id })
      }
    },
  }
}

// ─── 命令执行 ─────────────────────────────────────────

/**
 * 解析输入的原始字符串并执行对应命令。
 *
 * ## 流程
 * 1. 空输入 → 跳过
 * 2. 回显命令行到输出（`> whoami`）
 * 3. 加入命令历史
 * 4. 查找注册表 → 不存在则报 notFound
 * 5. 权限检查 → 不满足则报 permissionDenied
 * 6. 执行命令 → 追加输出行 → 检测 __CLEAR__ 标记
 * 7. 自动滚动到底部
 *
 * @param raw - 原始输入字符串（去除前后空白前）
 */
function executeCommand(raw: string) {
  const trimmed = raw.trim()
  if (!trimmed) return

  // 回显：在输出中显示执行了什么命令
  lines.value.push(`${t('terminal.prompt')} ${trimmed}`)

  // 加入历史（非空命令）
  commandHistory.value.push(trimmed)
  // 重置导航索引，让 ↑ 从头（最新）开始
  historyIndex.value = -1

  // 解析命令名和参数：第一个空格前是命令名，之后是参数
  const [cmdName, ...args] = trimmed.split(/\s+/)
  const cmd = commandRegistry.get(cmdName)

  if (!cmd) {
    // 命令未找到时，检测是否是数学表达式（如 `1+1`、`2 ** 10`）
    // 这样用户无需输入 `calc` 前缀，直接写表达式即可
    if (isMathExpression(trimmed)) {
      lines.value.push(evaluateExpression(trimmed))
      scrollToBottom()
      return
    }
    lines.value.push(t('terminal.notFound', { cmd: cmdName }))
    scrollToBottom()
    return
  }

  // 权限检查：高权限命令 + 低权限用户 → 拒绝
  const ctx = buildContext()
  if (cmd.requiredPrivilege === 'ADMIN' && ctx.privilegeClass !== 'ADMIN') {
    lines.value.push(t('terminal.permissionDenied', { cmd: cmdName }))
    scrollToBottom()
    return
  }

  // 执行命令，捕获内部异常防止终端崩溃
  try {
    const output = cmd.execute(args, ctx)
    // clear 命令返回特殊标记，由终端清空 lines 数组
    if (output.length === 1 && output[0] === CLEAR_MARKER) {
      lines.value.length = 0
      return
    }
    lines.value.push(...output)
  } catch (err) {
    console.error(`[Terminal] Command "${cmdName}" failed:`, err)
    lines.value.push(t('terminal.internalError', { cmd: cmdName }))
  }

  scrollToBottom()
}

// ─── 键盘处理 ─────────────────────────────────────────

/**
 * 隐藏 input 的 keydown 处理器。
 * Enter 执行命令，ArrowUp/Down 浏览历史，其余按键走浏览器默认行为。
 *
 * ArrowUp 需要 preventDefault()，否则光标会跳到输入框开头。
 * ArrowDown 同理。
 */
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    executeCommand(input.value)
    input.value = ''
    return
  }
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    navigateHistory(-1)
    return
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    navigateHistory(1)
    return
  }
}

// ─── 历史导航 ─────────────────────────────────────────

/**
 * 在命令历史中上下导航。
 *
 * ## 索引解释
 * `commandHistory` 按时间顺序存储：[较旧, ..., 较新]
 * `historyIndex` 映射：
 *   -1 → 当前新输入（不在历史中）
 *    0 → 最新一条 = commandHistory[length-1]
 *    1 → 倒数第二条 = commandHistory[length-2]
 *    N → 第 N 条历史 = commandHistory[length-1-N]
 *
 * @param direction - -1 表示上一条（更新），1 表示下一条（更旧）
 */
function navigateHistory(direction: -1 | 1) {
  if (commandHistory.value.length === 0) return

  const newIndex = historyIndex.value + direction

  // 边界检查：-1 是"不在历史中"的有效值，N 超过历史长度无效
  if (newIndex < -1 || newIndex >= commandHistory.value.length) return

  historyIndex.value = newIndex

  // 从最新一条开始取历史
  if (newIndex === -1) {
    input.value = ''
  } else {
    input.value = commandHistory.value[commandHistory.value.length - 1 - newIndex]
  }
}

// ─── 自动滚动 ─────────────────────────────────────────

/**
 * 将输出区域滚动到底部。
 * 使用 nextTick 确保 DOM 已更新后再设置 scrollTop。
 */
async function scrollToBottom() {
  await nextTick()
  if (outputRef.value) {
    outputRef.value.scrollTop = outputRef.value.scrollHeight
  }
}

// ─── 聚焦 ─────────────────────────────────────────────

/** 聚焦隐藏 input，使键盘输入被捕获 */
function focusInput() {
  hiddenInput.value?.focus()
}

// ─── 生命周期 ─────────────────────────────────────────

onMounted(() => {
  // 启动信息：模拟内核 boot 日志
  lines.value.push(t('terminal.boot.line1'))
  // boot.line2 为空字符串时跳过（预留扩展）
  const line2 = t('terminal.boot.line2')
  if (line2) lines.value.push(line2)

  // 自动聚焦，用户打开终端即可直接输入
  focusInput()
})
</script>

<template>
  <div
    class="terminal"
    role="application"
    :aria-label="t('applications.terminal.title')"
    @click="focusInput"
  >
    <!-- 输出区域：历史行 + 当前输入行 -->
    <div ref="outputRef" class="terminal__output">
      <!-- 历史输出行 -->
      <p
        v-for="(line, i) in lines"
        :key="i"
        class="terminal__line"
      >
        <span v-if="isHtmlLine(line)" v-html="stripHtmlMarker(line)" />
        <template v-else>{{ line }}</template>
      </p>

      <!-- 当前输入行（提示符 + 输入文本 + 闪烁光标） -->
      <div class="terminal__input-line">
        <span class="terminal__prompt">{{ t('terminal.prompt') }}</span>
        <span class="terminal__input-text">{{ input }}</span>
        <span class="terminal__cursor" aria-hidden="true">_</span>
      </div>
    </div>

    <!--
      隐藏 <input>：
      - 接收所有键盘输入（Enter / Arrow / 文本）
      - 渲染完全由上面的 .terminal__input-line 控制
      - position: absolute 移出视口但保持可聚焦
      - spellcheck="false" 关闭拼写检查（命令不是自然语言）
      - autocomplete="off" 关闭浏览器自动补全（命令不适用）
    -->
    <input
      ref="hiddenInput"
      v-model="input"
      class="terminal__hidden-input"
      type="text"
      :aria-label="t('terminal.inputLabel')"
      spellcheck="false"
      autocomplete="off"
      @keydown="handleKeydown"
    />
  </div>
</template>

<style scoped>
/* ── 终端主容器 ── */
.terminal {
  position: relative;
  height: 100%;
  overflow: hidden;
  /* 深色背景模拟真实终端 */
  background: var(--canvas);
  cursor: text;
}

/* ── 输出区域（可滚动） ── */
.terminal__output {
  height: 100%;
  overflow-y: auto;
  padding: 12px 18px;
  /* 等宽字体系终端本质 */
  font: 13px var(--font-mono);
  line-height: 1.5;
  color: var(--text-secondary);
  /* 允许文本选中但阻止不必要的用户交互 */
  user-select: text;
}

/* ── 单行输出 ── */
.terminal__line {
  margin: 0;
  padding: 1px 0;
  white-space: pre-wrap;
  word-break: break-all;
}

/* ── 当前输入行 ── */
.terminal__input-line {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 1px 0;
}

/* ── 提示符 ── */
.terminal__prompt {
  color: var(--signal-red-soft);
  margin-right: 6px;
  flex-shrink: 0;
}

/* ── 输入文本 ── */
.terminal__input-text {
  color: var(--text-secondary);
  white-space: pre-wrap;
}

/* ── 闪烁光标 ── */
.terminal__cursor {
  color: var(--text-primary);
  animation: terminal-blink 1s step-end infinite;
}

@keyframes terminal-blink {
  50% {
    opacity: 0;
  }
}

/* ── 隐藏 input（接收键盘事件但不渲染） ──

   为什么用 absolute + left: -9999px 而不是 display: none？
   display: none 的元素不可聚焦，无法接收键盘事件。
   而 visibility: hidden 在某些浏览器中仍会占据布局空间。
   移出视口是最可靠的"保持可聚焦但不可见"方案。
*/
.terminal__hidden-input {
  position: absolute;
  left: -9999px;
  width: 1px;
  height: 1px;
  opacity: 0;
  /* 确保浏览器不渲染 border/padding 影响布局 */
  border: 0;
  padding: 0;
  margin: 0;
}
</style>
