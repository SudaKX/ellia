/**
 * # AI 表情映射表
 *
 * 将 `AiExpression` 语义 key 映射到 public/images/ellia_little 下的表情图片。
 * 集中管理，新增表情只需在 AiExpression 与映射表中各加一项。
 */
import type { AiExpression } from './types'

export const AI_EXPRESSION_IMAGES: Record<AiExpression, string> = {
  normal: '/console/images/ellia_little/ellia_normal.png',
  smile: '/console/images/ellia_little/ellia_happy.png',
  happy: '/console/images/ellia_little/ellia_happy.png',
  'happy-tear': '/console/images/ellia_little/ellia_happy.png',
  speak: '/console/images/ellia_little/ellia_normal_speak.png',
  shock: '/console/images/ellia_little/ellia_confuse.png',
  awkward: '/console/images/ellia_little/ellia_dishappy.png',
  'very-awkward': '/console/images/ellia_little/ellia_cattiness.png',
  blush: '/console/images/ellia_little/ellia_shy.png',
  annoy: '/console/images/ellia_little/ellia_dishappy.png',
  angry: '/console/images/ellia_little/ellia_angry.png',
  urgent: '/console/images/ellia_little/ellia_angry.png',
  sad: '/console/images/ellia_little/ellia_dishappy.png',
  tear: '/console/images/ellia_little/ellia_dishappy.png',
}

/** 取表情图片 URL；未知 key 回退到常态 */
export function expressionImage(expression: AiExpression | undefined): string {
  return expression ? AI_EXPRESSION_IMAGES[expression] : AI_EXPRESSION_IMAGES.normal
}
