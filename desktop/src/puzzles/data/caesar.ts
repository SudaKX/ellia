/**
 * # 内置题目数据：凯撒密码（caesar-cipher）
 *
 * 原 ExampleCipher.vue 硬编码的凯撒密码谜题，改造成数据驱动定义，
 * 由通用播放器 PuzzlePlayer 渲染，题面/答案/提示与旧版完全等价。
 *
 * ## 多语言
 *
 * 标题、描述、提示通过 titleKey / textKey / hintKeys 引用 i18n key，
 * 与旧组件一致（各语言文件 puzzles.caesarCipher.* 段保持不变）。
 */

import type { PuzzleDefinition } from '@/types/puzzle'

export const CAESAR_DEFINITION: PuzzleDefinition = {
  id: 'caesar-cipher',
  title: 'Caesar Cipher',
  titleKey: 'puzzles.caesarCipher.title',
  blocks: [
    { type: 'text', text: '', textKey: 'puzzles.caesarCipher.description' },
    // 密文展示（等宽字体块，复刻旧版 code 样式）
    { type: 'text', text: 'khoor zruog', variant: 'code' },
  ],
  type: 'fill',
  fillAnswers: ['hello world'],
  hintKeys: ['puzzles.caesarCipher.hint1', 'puzzles.caesarCipher.hint2'],
}
