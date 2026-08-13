<script setup lang="ts">
/**
 * # MatrixRain — 01 红色故障闪烁背景
 *
 * 纯装饰性背景组件，在 `<canvas>` 上以不规则节奏快速闪烁 01 二进制字符。
 * 红色字符 + 随机开关周期 + 偶发故障爆发 → glitch 警示美学。
 * 不拦截鼠标/触控事件（pointer-events: none），不影响桌面交互。
 *
 * ## 用法
 *
 * ```vue
 * <MatrixRain />
 * <MatrixRain :options="{ color: '#e34d55', density: 0.4 }" />
 * ```
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useMatrixRain, type MatrixRainOptions } from '@/composables/useMatrixRain'

const props = withDefaults(
  defineProps<{
    /** 覆盖默认配置（全部可选） */
    options?: Partial<MatrixRainOptions>
  }>(),
  {
    options: () => ({}),
  },
)

const canvasRef = ref<HTMLCanvasElement | null>(null)
const rain = useMatrixRain(props.options)

onMounted(async () => {
  if (canvasRef.value) {
    await rain.init(canvasRef.value)
  }
})

onBeforeUnmount(() => {
  rain.destroy()
})
</script>

<template>
  <canvas ref="canvasRef" class="matrix-rain" aria-hidden="true" />
</template>

<style scoped>
.matrix-rain {
  position: absolute;
  inset: 0;
  z-index: 0;
  display: block;
  pointer-events: none;
  user-select: none;
}
</style>
