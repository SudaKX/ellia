/**
 * # AI 表情映射表
 *
 * 将 `AiExpression` 语义 key 映射到 public/images/kei 下的表情图片。
 * 集中管理，新增表情只需在 AiExpression 与映射表中各加一项。
 */
import type { AiExpression } from './types'

export const AI_EXPRESSION_IMAGES: Record<AiExpression, string> = {
  normal: '/console/images/kei/kei_normal1.webp',
  smile: '/console/images/kei/kei_smile1.webp',
  happy: '/console/images/kei/kei_happy2.webp',
  'happy-tear': '/console/images/kei/kei_happy_to_tear.webp',
  speak: '/console/images/kei/kei_speak1.webp',
  shock: '/console/images/kei/kei_shock1.webp',
  awkward: '/console/images/kei/kei_awkward.webp',
  'very-awkward': '/console/images/kei/kei_veryawkward.webp',
  blush: '/console/images/kei/kei_让我看看!(脸红).webp',
  annoy: '/console/images/kei/kei_annoy1.webp',
  angry: '/console/images/kei/kei_大急.webp',
  urgent: '/console/images/kei/kei_睁眼大急.webp',
  sad: '/console/images/kei/kei_大悲.webp',
  tear: '/console/images/kei/kei_超大悲_tear.webp',
}

/** 取表情图片 URL；未知 key 回退到常态 */
export function expressionImage(expression: AiExpression | undefined): string {
  return expression ? AI_EXPRESSION_IMAGES[expression] : AI_EXPRESSION_IMAGES.normal
}
