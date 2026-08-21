/**
 * # useStoryDialog — 交互剧情窗口服务（创作者 API）
 *
 * 为剧情/谜题创作者提供"数据驱动"的交互剧情播放能力：
 * 创作者只需写一份 `StoryNode[]` 脚本，其余演出（打字机、选项、滑杆、
 * 跳转、音频、成就）全部由本服务 + StoryDialog.vue 完成。
 *
 * ## 创作者 API 一览
 *
 * ```ts
 * import { playStoryScript } from '@/composables/useStoryDialog'
 *
 * const script: StoryNode[] = [
 *   { id: 'welcome', speaker: 'JDK', text: '欢迎来到【FAKE_OS】。', next: 'e-arrive' },
 *   {
 *     id: 'e-arrive', speaker: 'E', text: '你来了。你想做什么？',
 *     choices: [
 *       { label: '看看文件', next: 'e-files' },
 *       { label: '你是谁', next: 'e-who' },
 *     ],
 *   },
 *   {
 *     id: 'e-trust', speaker: 'E', text: '你信我吗？',
 *     slider: {
 *       label: '信任程度', min: 0, max: 100,
 *       next: (value) => (value >= 70 ? 'e-high' : 'e-low'),
 *     },
 *   },
 * ]
 *
 * playStoryScript(script)
 * ```
 *
 * ## 节点（StoryNode）语义
 *
 * - **纯对白**：`text` 打字机输出，点击继续 → `next`（缺省 = 顺序下一个）
 * - **多选**：`choices`（**最多 4 个**，超出部分忽略并警告）→ 点击选项按 `next` 跳转
 * - **滑杆**：`slider`（调节型选项）→ 玩家拖动后提交，按 `next(value)` 返回的 id 跳转
 * - **副作用**：节点 `effect()` 进入时执行；选项 `effect()` 点击时执行
 *   （可解锁成就、播放音频等，复用 useAchievementUnlocks / useAudioService）
 * - `choices` 与 `slider` 互斥；`id` 缺省自动生成（`node-${i}`），
 *   显式 id 用于跳转目标，创作者应给重要分支节点命名
 *
 * ## 约束（给创作者）
 *
 * - 选项数量 1 ~ 4；滑杆提交返回的 id 必须存在于脚本中（否则顺序下一个）
 * - 剧本文本为**内容数据**，不参与 i18n（与文件系统内容一致）；
 *   UI 文案（继续 / 提交按钮）由组件走 i18n
 *
 * ## 与 AiAssistant 的区别
 *
 * AiAssistant 是 kei 形象的彩蛋浮动窗；本服务是正式的交互剧情引擎（模态窗口）。
 *
 * ## 模块级单例
 *
 * 模块级函数无法 inject，DesktopView setup 时 `initStoryDialog(windowService)` 注册
 * 唯一的 WindowService 实例（与 useAchievementUnlocks 注入 AudioService 同模式）。
 */

import { markRaw } from 'vue'
import { Bot } from 'lucide-vue-next'

import GalStoryDialog from '@/components/desktop/GalStoryDialog.vue'
import type { WindowService } from '@/composables/useWindowService'

/** 玩家选项（1 ~ 4 个） */
export interface StoryChoice {
  /** 选项按钮文案（内容数据） */
  label: string
  /** 跳转目标节点 id；缺省 = 顺序下一个 */
  next?: string
  /** 选择时执行的副作用（解锁成就、播放音频等）；可选 */
  effect?: () => void
}

/** 滑杆调节选项（"滑动变阻器"式输入） */
export interface StorySlider {
  /** 滑杆标签文案 */
  label: string
  /** 最小值 */
  min: number
  /** 最大值 */
  max: number
  /** 步进；缺省 1 */
  step?: number
  /** 初始值；缺省 = (min+max)/2 */
  initial?: number
  /** 提交按钮文案；缺省用 i18n story.dialog.submit */
  submitLabel?: string
  /** 提交后按当前值返回目标节点 id */
  next: (value: number) => string
  /** 提交时副作用；可选 */
  effect?: (value: number) => void
}

export interface StoryStageCharacter {
  id: string
  image: string
  position: 'left' | 'center' | 'right'
  speakerNames: string[]
  animation?: 'fade' | 'slide-left' | 'slide-right' | 'rise' | 'none'
  /** 立绘展示范围；top-third 只保留原图顶部三分之一 */
  crop?: 'full' | 'top-third'
}

/** 剧情节点（对白 / 多选 / 滑杆） */
export interface StoryNode {
  /** 节点唯一 id（跳转目标）；缺省由播放器生成 */
  id?: string
  /** 说话者标签（如 'E'、'JDK'、'P'）；缺省不显示 */
  speaker?: string
  /** 台词正文（内容数据，不参与 i18n） */
  text?: string
  /** 节点配图 URL（如 /images/...） */
  image?: string
  /** 舞台图像位置；缺省为 center */
  imagePosition?: 'left' | 'center' | 'right'
  /** 舞台图像的入场演出；缺省为 fade */
  imageAnimation?: 'fade' | 'slide-left' | 'slide-right' | 'rise' | 'none'
  /** 节点进入时并行播放的音频 URL */
  audio?: string
  /** 持续显示于舞台中的角色立绘；缺省时继承之前节点的设置 */
  stageCharacters?: StoryStageCharacter[]
  /** 玩家选项（1~4 个）；与 slider 互斥 */
  choices?: StoryChoice[]
  /** 滑杆调节；与 choices 互斥 */
  slider?: StorySlider
  /** 对白读完点击继续后的去向：目标节点 id；缺省 = 顺序下一个 */
  next?: string
  /** 节点进入时执行的副作用（解锁成就、播放音频等）；可选 */
  effect?: () => void
}

/** 对话窗口显示配置 */
export interface StoryDialogOptions {
  /** 是否启用 glitch 滤镜（E 不稳定的叙事暗示）；默认 false */
  glitch?: boolean
  /** 打字速度（每字符毫秒）；默认 30 */
  charDelay?: number
  /** 自动播放下每句完整台词停留时间（ms） */
  autoDelay?: number
}

/** 选项数量上限（创作者约束：不超过 4 个） */
export const MAX_CHOICES = 4

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
 * 播放一段交互剧情（模态窗口）。
 *
 * 归一化处理：为缺省 id 的节点自动编号、校验选项数量上限。
 *
 * @param script  - 剧情节点数组（数据驱动）
 * @param options - 显示配置（glitch 滤镜、打字速度）
 */
export function playStoryScript(script: StoryNode[], options: StoryDialogOptions = {}): void {
  if (!windowService || script.length === 0) return

  // 归一化：无 id 的节点自动编号
  const nodes = script.map((node, index) => ({
    ...node,
    id: node.id ?? `node-${index}`,
  }))

  // 约束校验：选项不超过 4 个
  for (const node of nodes) {
    if (node.choices && node.choices.length > MAX_CHOICES) {
      console.warn(
        `[story] 节点 "${node.id}" 有 ${node.choices.length} 个选项，超过上限 ${MAX_CHOICES}，超出部分将被忽略`,
      )
    }
  }

  windowService.send({
    type: 'create-window',
    payload: {
      titleKey: 'story.dialog.title',
      icon: markRaw(Bot),
      component: markRaw(GalStoryDialog),
      componentProps: { nodes, charDelay: options.charDelay ?? 30, autoDelay: options.autoDelay ?? 1100 },
      defaultWidth: 860,
      defaultHeight: 560,
      placement: 'center',
      mode: 'modal',
      resizable: false,
      filters: options.glitch ? { glitch: true } : undefined,
      controls: { minimize: false, close: true },
      maximizable: false,
    },
  })
}
