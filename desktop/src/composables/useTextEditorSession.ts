/**
 * # useTextEditorSession — 文本编辑器会话注册表
 *
 * 在"编辑器组件"与"DesktopView 的窗口关闭拦截"之间建立桥梁。
 *
 * ## 为什么需要它
 *
 * WindowFrame 标题栏的 X 按钮关闭行为由 DesktopView 通过 `closeAction` prop 接管
 * （与 AI 助手窗口的拦截方式一致）。但"是否已修改、是否需要弹保存提示"这些状态
 * 只存在于编辑器组件内部，DesktopView 无法直接得知。
 *
 * 本模块提供一个按 windowId 索引的模块级响应式 Map：
 * - 编辑器组件挂载时注册会话（含 `modified` 与 `requestClose` 回调）
 * - DesktopView 的 closeAction 通过 `requestTextEditorClose(windowId)` 委托给编辑器
 *
 * 采用模块级单例（非 Pinia store）的原因与 useFileSystem 一致：
 * 数据只在窗口生命周期内存在，且被组件树外的窗口系统消费，无需全局状态管理。
 *
 * ## 数据流
 *
 * ```
 * 标题栏 X 点击
 *   → DesktopView :close-action → requestTextEditorClose(windowId)
 *     → 有会话 → session.requestClose()  （编辑器自行决定：提示 / 直接关闭）
 *     → 无会话 → 返回 false，DesktopView 按普通窗口关闭
 * ```
 *
 * ## 使用示例
 *
 * ```ts
 * // 编辑器组件内
 * onMounted(() => {
 *   registerTextEditorSession(props.windowId, {
 *     get modified() { return isModified.value },
 *     requestClose,
 *   })
 * })
 * onBeforeUnmount(() => unregisterTextEditorSession(props.windowId))
 *
 * // DesktopView 内
 * function handleDockableWindowClose(windowId: string) {
 *   if (requestTextEditorClose(windowId)) return
 *   windowService.send({ type: 'close-window', windowId })
 * }
 * ```
 */

import { reactive } from 'vue'

/** 单个文本编辑器会话 */
export interface TextEditorSession {
  /** 是否有未保存的修改（响应式，供调用方读取当前值） */
  modified: boolean
  /** 关闭请求回调：由编辑器实现"提示保存 / 直接关闭"的分支逻辑 */
  requestClose: () => void
  /** 保存回调（Ctrl/Cmd+S 全局快捷键触发） */
  save: () => void
  /**
   * 焦点命中判断：判断给定元素是否位于该编辑器根元素内。
   * 全局保存快捷键据此决定"焦点在哪个编辑器"。
   */
  containsElement: (el: Node | null) => boolean
}

/** 按窗口 ID 索引的会话表（模块级单例） */
const sessions = reactive(new Map<string, TextEditorSession>())

/**
 * 注册编辑器会话。组件挂载时调用。
 *
 * @param windowId - 编辑器窗口 ID（由 FileExplorer 创建窗口后回填）
 * @param session  - 会话对象（含 modified 与 requestClose）
 */
export function registerTextEditorSession(windowId: string, session: TextEditorSession): void {
  sessions.set(windowId, session)
}

/**
 * 注销编辑器会话。组件卸载时调用，避免内存泄漏。
 *
 * @param windowId - 编辑器窗口 ID
 */
export function unregisterTextEditorSession(windowId: string): void {
  sessions.delete(windowId)
}

/**
 * 请求编辑器窗口关闭（DesktopView 的 closeAction 调用）。
 *
 * @param windowId - 窗口 ID
 * @returns true 表示已交由编辑器处理（修改提示等）；false 表示无会话，调用方可正常关闭窗口
 */
export function requestTextEditorClose(windowId: string): boolean {
  const session = sessions.get(windowId)
  if (!session) return false
  session.requestClose()
  return true
}

/**
 * 全局保存快捷键（Ctrl/Cmd+S）处理：找到**焦点所在**的编辑器并保存。
 *
 * 由 App.vue 的全局键盘拦截统一调用，因此监听只需注册一次：
 * - 焦点落在某个编辑器根元素内 → 触发该编辑器的保存，返回 true
 * - 焦点不在任何编辑器（或非 Ctrl/Cmd+S）→ 不保存，返回 false（无动作）
 *
 * @param event - 全局 keydown 事件
 * @returns true 表示已由某个编辑器处理（调用方应 preventDefault）
 */
export function handleGlobalSaveShortcut(event: KeyboardEvent): boolean {
  if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 's') return false
  const active = document.activeElement
  for (const session of sessions.values()) {
    if (session.containsElement(active)) {
      session.save()
      return true
    }
  }
  return false
}
