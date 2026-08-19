/**
 * # AI 贴合/分离图标
 *
 * 自绘极简 SVG（24×24 viewBox，stroke 风格与 lucide-vue-next 一致），
 * lucide 无 "><" / "<>" 的精确形状，故手绘两条折线：
 *
 * - AiAttachIcon（贴合）`><`：两个角尖向中间聚拢（对接）
 * - AiDetachIcon（分离）`<>`：两个角尖向外张开（脱离）
 */
import { defineComponent, h } from 'vue'

/** 由两条折线生成图标组件（props 与 lucide 对齐：size / strokeWidth） */
function createGlyph(firstPath: string, secondPath: string) {
  return defineComponent({
    name: 'AiLiaisonGlyph',
    props: {
      size: { type: Number, default: 14 },
      strokeWidth: { type: Number, default: 1.8 },
    },
    setup(props) {
      return () =>
        h(
          'svg',
          {
            width: props.size,
            height: props.size,
            viewBox: '0 0 24 24',
            fill: 'none',
            stroke: 'currentColor',
            'stroke-width': props.strokeWidth,
            'stroke-linecap': 'round',
            'stroke-linejoin': 'round',
          },
          [h('path', { d: firstPath }), h('path', { d: secondPath })],
        )
    },
  })
}

/**
 * 贴合（><）：左半尖朝右中、右半尖朝左中，两尖在中间相对且明显分开
 * （顶点 x=8 / x=16，中间留 8px 空隙，避免像 "X" 交叉）
 */
export const AiAttachIcon = createGlyph('M3 5 L8 12 L3 19', 'M21 5 L16 12 L21 19')

/** 分离（<>）：左半尖朝左、右半尖朝右，两尖向外张开 */
export const AiDetachIcon = createGlyph('M10 5 L4 12 L10 19', 'M14 5 L20 12 L14 19')
