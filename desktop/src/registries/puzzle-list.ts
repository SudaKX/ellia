/**
 * # 谜题注册入口
 *
 * 本文件通过副作用 import 注册所有谜题。
 * 在应用入口（DesktopView.vue）中 import 本文件即可触发注册。
 *
 * ## 谜题开发者操作指南
 *
 * 1. 在 `components/puzzles/` 下创建谜题 Vue 组件
 * 2. 在下方添加 `registerPuzzle()` 调用
 * 3. 在 i18n 文件中添加 `puzzles.<id>.*` 翻译段
 *
 * @example
 * ```ts
 * registerPuzzle({
 *   id: 'my-puzzle',
 *   nameKey: 'puzzles.myPuzzle.title',
 *   descriptionKey: 'puzzles.myPuzzle.description',
 *   component: defineAsyncComponent(() => import('@/components/puzzles/MyPuzzle.vue')),
 *   defaultWidth: 600,
 *   defaultHeight: 400,
 * })
 * ```
 */

import { defineAsyncComponent } from 'vue'
import { registerPuzzle } from '@/registries/puzzles'

registerPuzzle({
  id: 'caesar-cipher',
  nameKey: 'puzzles.caesarCipher.title',
  descriptionKey: 'puzzles.caesarCipher.description',
  component: defineAsyncComponent(() => import('@/components/puzzles/ExampleCipher.vue')),
  defaultWidth: 520,
  defaultHeight: 400,
})
