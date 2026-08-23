/**
 * # AI 对话剧本注册表
 *
 * 贴边对话窗贴合目标窗口后，按 key 解析开场剧本：
 * 谜题 id（host.componentProps.puzzleId）> 应用 id（host.applicationId）> 'default'。
 *
 * 台词与选项文案均为 i18n key（`aiScripts.*`），渲染时由 AiAssistant 的 `t()` 翻译，
 * 各语言翻译见 `src/i18n/locales/*` 的 `aiScripts` 词条。
 *
 * 注：输错次数等**联动事件的响应剧本**由 AiAssistant 内部按事件组装
 * （effect 需要访问积分 Store 与目标窗口操作，与宿主上下文强绑定），
 * 本注册表只承载"贴合开场"的静态内容。
 */
import type { WindowInstance } from '@/types/desktop'

import type { AiNode, AiScriptKey } from '../types'

/** 通用剧本：无专属剧本时播放（贴合到普通窗口 / 未贴合时的兜底） */
const defaultScript: AiNode[] = [
  {
    id: 'default-hello',
    expression: 'smile',
    text: 'aiScripts.default.hello',
    choices: [
      { label: 'aiScripts.default.helloChat', next: 'default-chat' },
      { label: 'aiScripts.default.helloQuiet', next: 'default-quiet' },
    ],
  },
  {
    id: 'default-chat',
    expression: 'normal',
    text: 'aiScripts.default.chat',
    next: 'default-end',
  },
  {
    id: 'default-quiet',
    expression: 'annoy',
    text: 'aiScripts.default.quiet',
    next: 'default-end',
  },
  {
    id: 'default-end',
    expression: 'normal',
    text: 'aiScripts.default.end',
  },
]

/** 文件浏览器剧本 */
const filesScript: AiNode[] = [
  {
    id: 'files-hello',
    expression: 'normal',
    text: 'aiScripts.files.hello',
    choices: [
      { label: 'aiScripts.files.helloWorth', next: 'files-tip' },
      { label: 'aiScripts.files.helloOk', next: 'files-end' },
    ],
  },
  {
    id: 'files-tip',
    expression: 'smile',
    text: 'aiScripts.files.tip',
    next: 'files-end',
  },
  {
    id: 'files-end',
    expression: 'normal',
    text: 'aiScripts.files.end',
  },
]

/** 终端剧本 */
const terminalScript: AiNode[] = [
  {
    id: 'terminal-hello',
    expression: 'smile',
    text: 'aiScripts.terminal.hello',
    choices: [
      { label: 'aiScripts.terminal.helloLs', next: 'terminal-ls' },
      { label: 'aiScripts.terminal.helloOk', next: 'terminal-end' },
    ],
  },
  {
    id: 'terminal-ls',
    expression: 'normal',
    text: 'aiScripts.terminal.ls',
    next: 'terminal-end',
  },
  {
    id: 'terminal-end',
    expression: 'normal',
    text: 'aiScripts.terminal.end',
  },
]

/** 凯撒密码谜题剧本 */
const caesarCipherScript: AiNode[] = [
  {
    id: 'caesar-hello',
    expression: 'smile',
    text: 'aiScripts.caesar.hello',
    choices: [
      { label: 'aiScripts.caesar.helloHow', next: 'caesar-tip' },
      { label: 'aiScripts.caesar.helloTry', next: 'caesar-end' },
    ],
  },
  {
    id: 'caesar-tip',
    expression: 'normal',
    text: 'aiScripts.caesar.tip',
    next: 'caesar-end',
  },
  {
    id: 'caesar-end',
    expression: 'normal',
    text: 'aiScripts.caesar.end',
  },
]

/** 剧本注册表：AiScriptKey → 节点数组 */
export const aiScripts: Record<AiScriptKey, AiNode[]> = {
  default: defaultScript,
  files: filesScript,
  terminal: terminalScript,
  'caesar-cipher': caesarCipherScript,
}

/**
 * 按目标窗口解析剧本：
 * 谜题 id（componentProps.puzzleId）> 应用 id（applicationId）> default。
 *
 * @param hostWindow - 当前贴合的目标窗口；null 时返回 default
 */
export function resolveScript(hostWindow: WindowInstance | null): AiNode[] {
  if (!hostWindow) return aiScripts.default

  // 谜题窗口（applicationId 为 null，componentProps.puzzleId 标识谜题）
  const puzzleId = hostWindow.componentProps.puzzleId as string | undefined
  if (puzzleId && aiScripts[puzzleId]) {
    return aiScripts[puzzleId]
  }

  // 注册表应用
  if (hostWindow.applicationId && aiScripts[hostWindow.applicationId]) {
    return aiScripts[hostWindow.applicationId]
  }

  return aiScripts.default
}
