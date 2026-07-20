/**
 * # 桌面类型定义
 *
 * 本文件定义了 FakeOS 桌面的核心数据结构。
 *
 * ## 类型层次
 *
 * ```
 * ApplicationId            — 应用标识（'files' | 'archive' | 'terminal' | 'sandbox'）
 * DesktopApplication       — 静态应用元数据（名称、描述、可用状态）
 *
 * WindowDefinition         — 窗口创建模板（不含 id）
 * ApplicationDescriptor    — 扩展 WindowDefinition，添加了 id（用于 registry 注册）
 * CreateWindowPayload      — 扩展 WindowDefinition，可选 applicationId（用于消息总线）
 *
 * WindowInstance           — 运行时窗口实例（含位置、大小、状态等动态属性）
 * WindowMessage            — 消息总线联合类型（4 种消息）
 *
 * WindowControls           — 窗口控件开关（minimize / close）
 * WindowPlacement          — 窗口初始位置策略（'cascade' | 'center'）
 * WindowMode               — 窗口模式（'normal' | 'modal'）
 * WindowFilters            — 窗口滤镜开关映射
 * ```
 *
 * ## 设计原则
 *
 * 1. **模板与实例分离**：`WindowDefinition` 描述"怎么创建"，`WindowInstance` 描述"当前状态"
 * 2. **消息总线**：窗口操作通过 `WindowMessage` 传递，组件无需直接持有 WindowService 引用
 * 3. **双层模态**：`WindowMode.modal` 窗口阻断普通窗口的交互，通过 z-index 分层实现
 * 4. **滤镜系统**：`WindowFilters` 按 `FilterType` 映射 boolean，决定是否启用 glitch 等效果
 *
 * ## 与 dev_frontend_darksky 分支的区别
 *
 * 本分支保留了完整的模态窗口、消息总线、色差偏移等能力。
 * darksky 分支将这些能力移除，采用更扁平化的设计。
 * 保留完整版是因为模态弹窗对"权限拒绝""网络断开"等叙事场景是刚需。
 */

import type { Component } from 'vue'

import type { FilterType } from '@/registries/filters'

export type ApplicationId = 'files' | 'archive' | 'terminal' | 'sandbox'

/** 静态应用元数据，用于 Launchpad 展示 */
export interface DesktopApplication {
  id: ApplicationId
  name: string
  description: string
  group: string
  availability: 'available' | 'locked'
}

/** 窗口初始位置策略 */
export type WindowPlacement = 'cascade' | 'center'
/** 窗口模式：normal（普通）| modal（模态弹窗） */
export type WindowMode = 'normal' | 'modal'
/** 窗口滤镜开关：FilterType → 是否启用 */
export type WindowFilters = Partial<Record<FilterType, boolean>>

/** 窗口控件可见性开关 */
export interface WindowControls {
  minimize: boolean
  close: boolean
}

/** 窗口创建模板（不含运行时 id），可被 ApplicationDescriptor 和 CreateWindowPayload 复用 */
export interface WindowDefinition {
  title: string
  icon: Component
  component: Component
  defaultWidth: number
  defaultHeight: number
  componentProps?: Record<string, unknown>
  controls?: Partial<WindowControls>
  placement?: WindowPlacement
  mode?: WindowMode
  resizable?: boolean
  filters?: WindowFilters
}

/** 应用注册表中的条目：WindowDefinition + 唯一 id */
export interface ApplicationDescriptor extends WindowDefinition {
  id: ApplicationId
}

/** 消息总线中 create-window 的 payload：WindowDefinition + 可选 applicationId */
export interface CreateWindowPayload extends WindowDefinition {
  applicationId?: ApplicationId
}

/** 窗口操作消息总线联合类型 */
export type WindowMessage =
  | { type: 'create-window'; payload: CreateWindowPayload }
  | { type: 'close-window'; windowId: string }
  | { type: 'minimize-window'; windowId: string }
  | { type: 'focus-window'; windowId: string }

/** 运行时窗口实例 */
export interface WindowInstance {
  id: string
  applicationId: ApplicationId | null
  title: string
  icon: Component
  component: Component
  componentProps: Record<string, unknown>
  controls: WindowControls
  mode: WindowMode
  resizable: boolean
  filters: WindowFilters
  x: number
  y: number
  width: number
  height: number
  zIndex: number
  isMinimized: boolean
}
