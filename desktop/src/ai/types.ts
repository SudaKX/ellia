/**
 * # AI 对话剧本类型定义
 *
 * 贴边 AI 对话窗（AI Liaison）的数据结构：
 * - `AiNode`：对话节点（表情差分 + 文字 + ≤4 个选项），结构与 StoryNode 兼容
 * - `AiChoice`：玩家选项（最多 4 个），effect 可反向操作目标窗口
 * - `AiScriptKey`：剧本注册 key（'default' | 应用 id | 谜题 id）
 *
 * 与 StoryNode 的关系：AiNode 是其超集（多 expression 字段），
 * StoryDialog 引擎可忽略 expression 直接播放，二者互不干扰。
 *
 * ## 约定
 *
 * - 对话文本与选项文案均为 **i18n key**（`aiScripts.*`），渲染时由 AiAssistant 的
 *   `t()` 翻译；key 缺失时回退为 key 本身
 * - 选项数量 1 ~ 4，超出部分忽略
 */

/** AI 表情差分语义 key */
export type AiExpression =
  | 'normal'        // 常态
  | 'smile'         // 微笑
  | 'happy'         // 开心
  | 'happy-tear'    // 喜极而泣
  | 'speak'         // 开口说话
  | 'shock'         // 震惊
  | 'awkward'       // 尴尬
  | 'very-awkward'  // 非常尴尬
  | 'blush'         // 脸红
  | 'annoy'         // 不耐烦
  | 'angry'         // 生气（大急）
  | 'urgent'        // 着急（睁眼大急）
  | 'sad'           // 悲伤（大悲）
  | 'tear'          // 大哭（超大悲）

/** 玩家选项（1 ~ 4 个） */
export interface AiChoice {
  /** 选项按钮文案（i18n key，如 `aiScripts.default.helloChat`） */
  label: string
  /** 跳转目标节点 id；缺省 = 顺序下一个 */
  next?: string
  /** 选择时执行的副作用（扣积分、操作目标窗口等）；可选 */
  effect?: () => void
}

/** AI 对话节点 */
export interface AiNode {
  /** 节点唯一 id（跳转目标）；缺省由播放器自动编号 */
  id?: string
  /** kei 表情差分；缺省保持上一节点表情 */
  expression?: AiExpression
  /** 台词正文（i18n key，如 `aiScripts.default.hello`） */
  text?: string
  /** 玩家选项（1~4 个） */
  choices?: AiChoice[]
  /** 对白读完点击继续后的去向：目标节点 id；缺省 = 顺序下一个 */
  next?: string
  /** 节点进入时执行的副作用（解锁成就、播放音频等）；可选 */
  effect?: () => void
}

/** 剧本注册 key：'default' | 应用 id（files/terminal 等）| 谜题 id */
export type AiScriptKey = string

/** 目标窗口 → AI：联动事件名 */
export type AiEventName = 'puzzle-wrong' | 'puzzle-solved'

/** AI → 目标窗口：执行的操作名 */
export type AiHostAction = 'ai-open-hint' | 'ai-fill-answer'
