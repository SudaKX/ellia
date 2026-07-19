<script setup lang="ts">
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
