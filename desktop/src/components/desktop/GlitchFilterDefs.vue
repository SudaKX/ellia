<script setup lang="ts">
/**
 * # Glitch SVG 滤镜定义组件
 *
 * 渲染一个隐藏的 `<svg>`，内含完整的 Glitch 滤镜管线。
 * 通过 `filterId` 将滤镜注册到 DOM，其他元素可用 `filter: url(#filterId)` 引用。
 *
 * ## SVG 滤镜管线
 *
 * ```
 * SourceGraphic
 *   → feDisplacementMap (R→水平偏移, G→垂直偏移)  → "displaced"
 *   → feColorMatrix (只保留 R 通道)                → "red"
 *   → feOffset (R 通道左移)                         → "red-shifted"
 *   → feColorMatrix (只保留 G 通道)                → "green"
 *   → feOffset (G 通道右移)                         → "green-shifted"
 *   → feColorMatrix (只保留 B 通道)                → "blue"
 *   → feBlend (screen: red + green)                → "rg"
 *   → feBlend (screen: rg + blue)                  → 最终输出
 * ```
 *
 * ## 色差原理
 *
 * 将原始图像的 R/G/B 三通道分离，R 向左偏移、G 向右偏移、B 不偏移，
 * 再用 screen 模式合成，产生类似 CRT 色散的效果。
 * 偏移量由 `useGlitchFilter` 通过 `ref` 动态控制。
 *
 * ## 使用方式
 *
 * ```vue
 * <GlitchFilterDefs :filter-id="filterId" :options="options" />
 *
 * <!-- 其他组件引用 -->
 * <div :style="{ filter: `url(#${filterId})` }">...</div>
 * ```
 */

import { ref, toRef } from 'vue'

import { useGlitchFilter, type GlitchOptions } from '@/composables/useGlitchFilter'

const props = defineProps<{
  filterId: string
  options: GlitchOptions
}>()

const mapImage = ref<SVGFEImageElement | null>(null)
const displacement = ref<SVGFEDisplacementMapElement | null>(null)
const redOffset = ref<SVGFEOffsetElement | null>(null)
const greenOffset = ref<SVGFEOffsetElement | null>(null)

const emit = defineEmits<{
  ready: []
}>()

const { ready } = useGlitchFilter(toRef(props, 'options'), {
  mapImage,
  displacement,
  redOffset,
  greenOffset,
})

void ready.then(() => {
  emit('ready')
})
</script>

<template>
  <svg width="0" height="0" aria-hidden="true" style="display: none">
    <defs>
      <filter
        :id="filterId"
        x="-20%"
        y="-20%"
        width="140%"
        height="140%"
        filterUnits="objectBoundingBox"
        primitiveUnits="objectBoundingBox"
        color-interpolation-filters="sRGB"
      >
        <feImage
          ref="mapImage"
          x="0"
          y="0"
          width="1"
          height="1"
          preserveAspectRatio="none"
          result="canvas-map"
        />

        <feDisplacementMap
          ref="displacement"
          in="SourceGraphic"
          in2="canvas-map"
          scale="0.045"
          xChannelSelector="R"
          yChannelSelector="G"
          result="displaced"
        />

        <feColorMatrix
          in="displaced"
          type="matrix"
          values="
            1 0 0 0 0
            0 0 0 0 0
            0 0 0 0 0
            0 0 0 1 0
          "
          result="red"
        />

        <feOffset ref="redOffset" in="red" dx="-0.001" dy="0" result="red-shifted" />

        <feColorMatrix
          in="displaced"
          type="matrix"
          values="
            0 0 0 0 0
            0 1 0 0 0
            0 0 0 0 0
            0 0 0 1 0
          "
          result="green"
        />

        <feOffset ref="greenOffset" in="green" dx="0.001" dy="0" result="green-shifted" />

        <feColorMatrix
          in="displaced"
          type="matrix"
          values="
            0 0 0 0 0
            0 0 0 0 0
            0 0 1 0 0
            0 0 0 1 0
          "
          result="blue"
        />

        <feBlend in="red-shifted" in2="green-shifted" mode="screen" result="rg" />
        <feBlend in="rg" in2="blue" mode="screen" />
      </filter>
    </defs>
  </svg>
</template>
