/**
 * # 题目数据契约（Puzzle Definition）
 *
 * 与 desktop（FakeOS 游戏）共用同一契约（desktop/src/types/puzzle.ts 的同步副本）。
 * 出题器导出的 published-questions.json 即本格式的集合，供游戏自动发现。
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
 * 注意：desktop 版额外支持 titleKey / textKey / hintKeys（游戏内置题多语言用）；
 * 出题器只使用纯文本字段，不填 key 字段。
 */

/** 题面内容块 */
export type ContentBlock =
  | {
      type: 'text'
      /** 文本内容 */
      text: string
      /** 展示样式：code = 等宽字体块（密文等），缺省 normal */
      variant?: 'normal' | 'code'
    }
  | {
      type: 'image'
      /** 图片 URL */
      url: string
      /** 替代文本（无障碍） */
      alt?: string
      /** 图片说明 */
      caption?: string
    }
  | {
      type: 'video'
      /** 视频 URL */
      url: string
      /** 视频说明 */
      caption?: string
    }
  | {
      type: 'rich'
      /** HTML 字符串（审核后渲染） */
      html: string
    }

/** 题型：single 单选 / multi 多选 / fill 填空 */
export type QuestionType = 'single' | 'multi' | 'fill'

/** 选择题选项 */
export interface PuzzleOption {
  /** 选项文本 */
  text: string
  /** 是否正确答案 */
  correct?: boolean
}

/** 完整题目定义（数据驱动契约） */
export interface PuzzleDefinition {
  /** 唯一标识（.puz 文件名 / sil 命令参数） */
  id: string
  /** 题目标题 */
  title: string
  /** 题面（富媒体块列表） */
  blocks: ContentBlock[]
  /** 题型 */
  type: QuestionType
  /** 单选/多选题选项（2~10 个） */
  options?: PuzzleOption[]
  /** 填空题答案（一个或多个空，顺序对应） */
  fillAnswers?: string[]
  /** 提示列表（逐条揭示） */
  hints?: string[]
  /** 答后解析（可选） */
  explanation?: string
}
