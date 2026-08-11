/**
 * # 题目数据契约（Puzzle Definition）
 *
 * 数据驱动的通用题目格式，desktop（FakeOS 游戏）与 desktop_designer（出题器）
 * 共用同一契约，出题器导出的 `published-questions.json` 即本格式的集合。
 *
 * ## 结构
 *
 * - `blocks`：题面（富媒体块列表：文本 / 图片 / 视频 / 富文本）
 * - `type`：题型（single 单选 / multi 多选 / fill 填空）
 * - `options`：单选/多选题的选项（2~10 个，correct 标记正确答案）
 * - `fillAnswers`：填空题的答案（一个或多个空）
 * - `hints`：提示列表（逐条揭示）
 * - `explanation`：答后解析（可选）
 *
 * ## i18n 支持（仅游戏内置题使用）
 *
 * 游戏内置题（如 caesar-cipher）需要多语言，通过 `titleKey` / `textKey` /
 * `hintKeys` 引用 i18n key；出题器出的题只用纯文本字段（title / text / hints），
 * 不填 key 字段。
 *
 * ## @example
 *
 * ```ts
 * const definition: PuzzleDefinition = {
 *   id: 'caesar-cipher',
 *   titleKey: 'puzzles.caesarCipher.title',
 *   blocks: [{ type: 'text', textKey: 'puzzles.caesarCipher.description' }],
 *   type: 'fill',
 *   fillAnswers: ['hello world'],
 *   hintKeys: ['puzzles.caesarCipher.hint1'],
 * }
 * ```
 */

/** 题面内容块 */
export type ContentBlock =
  | {
      /** 文本段落 */
      type: 'text'
      /** 兜底文本（出题器使用）；游戏内置题可改用 textKey */
      text: string
      /** i18n key，存在时优先渲染翻译文本（游戏内置题多语言用） */
      textKey?: string
      /** 展示样式：code = 等宽字体块（密文等），缺省 normal */
      variant?: 'normal' | 'code'
    }
  | {
      /** 图片 */
      type: 'image'
      /** 图片 URL */
      url: string
      /** 替代文本（无障碍） */
      alt?: string
      /** 图片说明 */
      caption?: string
    }
  | {
      /** 视频 */
      type: 'video'
      /** 视频 URL */
      url: string
      /** 视频说明 */
      caption?: string
    }
  | {
      /** 富文本 HTML（内容经审核链把关，播放器 v-html 渲染） */
      type: 'rich'
      /** HTML 字符串 */
      html: string
    }

/** 题型：single 单选 / multi 多选 / fill 填空 */
export type QuestionType = 'single' | 'multi' | 'fill'

/** 选择题选项 */
export interface PuzzleOption {
  /** 选项文本 */
  text: string
  /** 是否正确答案（出题器标记；发布 JSON 一并下发供本地校验） */
  correct?: boolean
}

/** 完整题目定义（数据驱动契约） */
export interface PuzzleDefinition {
  /** 唯一标识（.puz 文件名 / sil 命令参数） */
  id: string
  /** 题目标题（兜底文本） */
  title: string
  /** 标题 i18n key，存在时优先渲染翻译文本（游戏内置题用） */
  titleKey?: string
  /** 题面（富媒体块列表） */
  blocks: ContentBlock[]
  /** 题型 */
  type: QuestionType
  /** 单选/多选题选项（2~10 个） */
  options?: PuzzleOption[]
  /** 填空题答案（一个或多个空，顺序对应） */
  fillAnswers?: string[]
  /** 提示列表（兜底文本，逐条揭示） */
  hints?: string[]
  /** 提示 i18n key 列表，存在时优先渲染翻译文本（游戏内置题用） */
  hintKeys?: string[]
  /** 答后解析（可选） */
  explanation?: string
}
