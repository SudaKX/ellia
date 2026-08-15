/**
 * # AI 对话剧本注册表
 *
 * 贴边对话窗贴合目标窗口后，按 key 解析开场剧本：
 * 谜题 id（host.componentProps.puzzleId）> 应用 id（host.applicationId）> 'default'。
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
    text: '……你把我拖过来了。怎么，需要帮忙？',
    choices: [
      { label: '随便聊聊', next: 'default-chat' },
      { label: '你先安静待着', next: 'default-quiet' },
    ],
  },
  {
    id: 'default-chat',
    expression: 'normal',
    text: '这个系统里的文件、谜题、终端……我都能看得见。你卡住了可以随时问我。',
    next: 'default-end',
  },
  {
    id: 'default-quiet',
    expression: 'annoy',
    text: '……好。我闭嘴。不过你摇一摇我，我就走。',
    next: 'default-end',
  },
  {
    id: 'default-end',
    expression: 'normal',
    text: '……我盯着你。别乱翻不该翻的东西。',
  },
]

/** 文件浏览器剧本 */
const filesScript: AiNode[] = [
  {
    id: 'files-hello',
    expression: 'normal',
    text: '你在翻文件。……学姐的文件系统里，藏着不少东西。双击就能打开，有些文件会触发剧情。',
    choices: [
      { label: '有哪些值得看？', next: 'files-tip' },
      { label: '知道了', next: 'files-end' },
    ],
  },
  {
    id: 'files-tip',
    expression: 'smile',
    text: '带 .puz 后缀的是谜题，双击能打开。init.exe 别乱动——那是开场剧情。',
    next: 'files-end',
  },
  {
    id: 'files-end',
    expression: 'normal',
    text: '……去吧。卡住了叫我。',
  },
]

/** 终端剧本 */
const terminalScript: AiNode[] = [
  {
    id: 'terminal-hello',
    expression: 'smile',
    text: '终端？有意思。用 help 看看命令，sil 可以打开谜题。',
    choices: [
      { label: '帮我看看文件', next: 'terminal-ls' },
      { label: '知道了', next: 'terminal-end' },
    ],
  },
  {
    id: 'terminal-ls',
    expression: 'normal',
    text: 'ls 列出当前目录，cat 读文件内容。这里的虚拟文件系统和剧情联动。',
    next: 'terminal-end',
  },
  {
    id: 'terminal-end',
    expression: 'normal',
    text: '……小心输入。别让命令跑进不该去的地方。',
  },
]

/** 凯撒密码谜题剧本 */
const caesarCipherScript: AiNode[] = [
  {
    id: 'caesar-hello',
    expression: 'smile',
    text: '凯撒密码？……字母移位而已。密文 "khoor zruog" 每个字母往前移 3 位。',
    choices: [
      { label: '具体怎么移？', next: 'caesar-tip' },
      { label: '我先自己试试', next: 'caesar-end' },
    ],
  },
  {
    id: 'caesar-tip',
    expression: 'normal',
    text: 'k→h，h→e，o→l……按字母表逐个回退 3 位。你要是输错太多次，我也可以帮你。',
    next: 'caesar-end',
  },
  {
    id: 'caesar-end',
    expression: 'normal',
    text: '……加油。实在不行再喊我。',
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
