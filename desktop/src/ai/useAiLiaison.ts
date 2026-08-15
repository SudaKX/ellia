/**
 * # useAiLiaison — AI 窗口与目标窗口的联动事件总线
 *
 * 模块级单例（与 useAchievementUnlocks 注入 AudioService 同模式），
 * 提供双向通道：
 *
 * - **目标窗口 → AI**：`notifyAi(sourceWindowId, event, payload)`
 *   AI 侧 `onAiEvent(cb)` 订阅，按来源窗口判断是否与当前贴合窗口一致。
 * - **AI → 目标窗口**：`sendHostAction(hostWindowId, action, payload)`
 *   目标窗口侧 `onHostAction(hostWindowId, cb)` 订阅（按窗口 id 精确路由）。
 *
 * ## 事件与操作约定
 *
 * - 事件：`puzzle-wrong`（谜题输错，payload 带 count）、`puzzle-solved`（已解）
 * - 操作：`ai-open-hint`（AI 开提示）、`ai-fill-answer`（AI 填答案，不提交）
 *
 * ## 使用示例
 *
 * ```ts
 * // 目标窗口（ExampleCipher）
 * const selfId = inject<string>(WINDOW_FRAME_ID)
 * notifyAi(selfId!, 'puzzle-wrong', { count: 2 })
 * const off = onHostAction(selfId!, (action) => {
 *   if (action === 'ai-fill-answer') userInput.value = 'hello world'
 * })
 * ```
 *
 * ```ts
 * // AI 窗口（AiAssistant）
 * const off = onAiEvent((event, payload, sourceId) => {
 *   if (sourceId === hostWindowId.value && event === 'puzzle-wrong') { ... }
 * })
 * ```
 */
import { shallowRef } from 'vue'

import type { AiEventName, AiHostAction } from './types'

type AiEventListener = (event: AiEventName, payload: unknown, sourceWindowId: string) => void
type HostActionListener = (action: AiHostAction, payload: unknown) => void

/** AI 侧订阅者集合 */
const aiListeners = new Set<AiEventListener>()
/** 目标窗口侧订阅者：windowId → listeners */
const hostActionListeners = new Map<string, Set<HostActionListener>>()

// ─── AI 窗口回调注册（DesktopView 经 WindowFrame prop 转发） ───

/**
 * AI 窗口当前状态（贴合/离开）。
 * 标题栏按钮据此切换图标与行为（DesktopView 读取）。
 */
const aiLiaisonState = shallowRef<'detached' | 'attached'>('detached')

/** 读取 AI 窗口状态（响应式） */
export function getAiLiaisonState(): typeof aiLiaisonState {
  return aiLiaisonState
}

/** 更新 AI 窗口状态（AiAssistant 在 attachTo/detach 时调用） */
export function setAiLiaisonState(state: 'detached' | 'attached'): void {
  aiLiaisonState.value = state
}

/** AI 窗口"贴合"处理器：贴合成功返回 true（由 AiAssistant 注册） */
let attachHandler: (() => boolean) | null = null

/**
 * 注册 AI 窗口的贴合处理器（AiAssistant setup 时调用，卸载时注销）。
 * 标题栏"贴合"按钮经 requestAiAttach 转发。
 */
export function registerAiAttach(handler: () => boolean): () => void {
  attachHandler = handler
  return () => {
    if (attachHandler === handler) attachHandler = null
  }
}

/** 请求 AI 窗口贴合到上一个焦点窗口；返回 true 表示已贴合 */
export function requestAiAttach(): boolean {
  return attachHandler ? attachHandler() : false
}

/** AI 窗口"分离"处理器：贴合态返回 true（已处理），离开态返回 false */
let detachHandler: (() => boolean) | null = null
/** AI 窗口拖拽回调（由 AiAssistant 注册，WindowFrame onDragMove/onDragEnd 转发） */
let dragMoveHandler: ((pos: { x: number; y: number }) => void) | null = null
let dragEndHandler: (() => void) | null = null

/**
 * 注册 AI 窗口的分离处理器（AiAssistant setup 时调用，卸载时注销）。
 * DesktopView 的关闭请求经 requestAiDetach 转发，贴合态走"分离"而非漂移。
 */
export function registerAiDetach(handler: () => boolean): () => void {
  detachHandler = handler
  return () => {
    if (detachHandler === handler) detachHandler = null
  }
}

/** 请求 AI 窗口分离（DesktopView 关闭键调用）；返回 true 表示已处理 */
export function requestAiDetach(): boolean {
  return detachHandler ? detachHandler() : false
}

/**
 * 注册 AI 窗口的拖拽回调（贴合检测 / 摇动检测）。
 * 由 DesktopView 在 WindowFrame 的 onDragMove/onDragEnd 中转发调用。
 */
export function registerAiDragHandlers(handlers: {
  onDragMove?: (pos: { x: number; y: number }) => void
  onDragEnd?: () => void
}): () => void {
  dragMoveHandler = handlers.onDragMove ?? null
  dragEndHandler = handlers.onDragEnd ?? null
  return () => {
    dragMoveHandler = null
    dragEndHandler = null
  }
}

/** 转发 AI 窗口拖动中回调 */
export function requestAiDragMove(pos: { x: number; y: number }): void {
  dragMoveHandler?.(pos)
}

/** 转发 AI 窗口拖动结束回调 */
export function requestAiDragEnd(): void {
  dragEndHandler?.()
}

/**
 * 目标窗口向 AI 上报事件。
 *
 * @param sourceWindowId - 发起事件的窗口 id（窗口自身 id）
 * @param event - 事件名
 * @param payload - 事件载荷（如 { count: 2 }）
 */
export function notifyAi(sourceWindowId: string, event: AiEventName, payload?: unknown): void {
  for (const listener of aiListeners) {
    listener(event, payload, sourceWindowId)
  }
}

/**
 * AI 侧订阅全部联动事件。
 *
 * @param listener - 事件回调（event / payload / 来源窗口 id）
 * @returns 取消订阅函数
 */
export function onAiEvent(listener: AiEventListener): () => void {
  aiListeners.add(listener)
  return () => {
    aiListeners.delete(listener)
  }
}

/**
 * AI 向目标窗口发送操作。
 *
 * @param hostWindowId - 目标窗口 id
 * @param action - 操作名
 * @param payload - 操作载荷
 */
export function sendHostAction(hostWindowId: string, action: AiHostAction, payload?: unknown): void {
  const listeners = hostActionListeners.get(hostWindowId)
  if (!listeners) return
  for (const listener of listeners) {
    listener(action, payload)
  }
}

/**
 * 目标窗口订阅 AI 操作（按自身窗口 id 精确路由）。
 *
 * @param hostWindowId - 自身窗口 id
 * @param listener - 操作回调
 * @returns 取消订阅函数
 */
export function onHostAction(hostWindowId: string, listener: HostActionListener): () => void {
  let listeners = hostActionListeners.get(hostWindowId)
  if (!listeners) {
    listeners = new Set()
    hostActionListeners.set(hostWindowId, listeners)
  }
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0) {
      hostActionListeners.delete(hostWindowId)
    }
  }
}
