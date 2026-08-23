/**
 * # windowFrameId — 窗口自身 id 的 provide/inject key
 *
 * WindowFrame 挂载时 provide 当前窗口的运行时 id，
 * 内容组件（谜题、AI 助手等）inject 后可用于：
 * - 向 AI 助手上报联动事件（useAiLiaison.notifyAi）
 * - 自我定位（如 AI 窗口贴合时更新自身几何）
 */
export const WINDOW_FRAME_ID = 'windowFrameId'
