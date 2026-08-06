/**
 * # useStoryDialog — 剧情对话窗口服务
 *
 * 提供"E 发送消息 → 玩家从多个选项中选择回复"的通用对话演出能力。
 * 配合 StoryDialog.vue 使用，通过 WindowService 创建模态窗口播放。
 *
 * ## 为什么是模块级单例
 *
 * - 对话可以从任意位置触发（开场、成就、事件、文件操作），不限于组件 setup
 * - 与 useFileSystem 的模式一致：模块级引用 + init 注册，无需 Pinia store
 * - DesktopView 持有唯一的 WindowService 实例，setup 时调用 initStoryDialog 注册
 *
 * ## 数据驱动脚本
 *
 * ```ts
 * openStoryDialog([
 *   { speaker: 'E', text: '你篡改了时间？' },
 *   { speaker: 'E', text: '你想做什么？', choices: [
 *     { label: '只是想帮忙', next: 3 },
 *     { label: '我找到了解放的线索' },
 *   ]},
 *   { speaker: 'P', text: '……' },
 * ])
 * ```
 *
 * - 无 choices 的台词：打字完成后点击任意处继续下一句
 * - 有 choices 的台词：必须点击选项，可跳到指定句（next）或执行动作（action）
 * - 播放完最后一句自动关闭窗口
 *
 * ## 与 AiAssistant 的区别
 *
 * AiAssistant 是 kei 形象的彩蛋浮动窗（标题栏台词滚动）；
 * 本组件是正式的剧情演出（模态窗口 + 逐句打字 + 玩家选项），互不替代。
 *
 * ## @example
 *
 * ```ts
 * import { initStoryDialog, openStoryDialog } from '@/composables/useStoryDialog'
 *
 * // DesktopView setup：
 * initStoryDialog(windowService)
 *
 * // 任意位置触发：
 * openStoryDialog([{ speaker: 'E', text: '你好，玩家。' }])
 * ```
 */

import { markRaw } from 'vue'
import { Bot } from 'lucide-vue-next'

import StoryDialog from '@/components/desktop/StoryDialog.vue'
import type { WindowService } from '@/composables/useWindowService'

/** 单条台词 */
export interface StoryLine {
  /** 说话者标签（如 'E'、'JDK'、'P'），显示在台词上方；缺省不显示 */
  speaker?: string
  /** 台词正文（剧情数据，非 UI 文案，不参与 i18n） */
  text: string
  /** 玩家可选回复；缺省 = 点击任意处继续下一句 */
  choices?: StoryChoice[]
}

/** 玩家可选回复 */
export interface StoryChoice {
  /** 选项按钮文案（剧情数据） */
  label: string
  /** 选择后跳转到剧本第几句；缺省 = 下一句 */
  next?: number
  /** 选择后执行的动作（如触发事件）；可选 */
  action?: () => void
}

/** 对话窗口显示配置 */
export interface StoryDialogOptions {
  /** 是否启用 glitch 滤镜（E 不稳定的叙事暗示）；默认 false */
  glitch?: boolean
  /** 打字速度（每字符毫秒）；默认 30 */
  charDelay?: number
}

let windowService: WindowService | null = null

/**
 * 注册 WindowService 实例（DesktopView setup 阶段调用一次）。
 *
 * @param service - 桌面唯一的窗口服务实例
 */
export function initStoryDialog(service: WindowService): void {
  windowService = service
}

/**
 * 打开剧情对话窗口（模态）。
 *
 * @param lines    - 台词脚本（数据驱动）
 * @param options  - 显示配置（glitch 滤镜、打字速度）
 */
export function openStoryDialog(lines: StoryLine[], options: StoryDialogOptions = {}): void {
  if (!windowService || lines.length === 0) return

  windowService.send({
    type: 'create-window',
    payload: {
      titleKey: 'story.dialog.title',
      icon: markRaw(Bot),
      component: markRaw(StoryDialog),
      componentProps: { lines, charDelay: options.charDelay ?? 30 },
      defaultWidth: 520,
      defaultHeight: 300,
      placement: 'center',
      mode: 'modal',
      resizable: false,
      filters: options.glitch ? { glitch: true } : undefined,
      controls: { minimize: false, close: true },
    },
  })
}
