import type { Component } from 'vue'

import type { FilterType } from '@/filters'

export type ApplicationId = 'files' | 'archive' | 'terminal' | 'sandbox'

export interface DesktopApplication {
  id: ApplicationId
  name: string
  description: string
  group: string
  availability: 'available' | 'locked'
}

export type WindowPlacement = 'cascade' | 'center'
export type WindowMode = 'normal' | 'modal'
export type WindowFilters = Partial<Record<FilterType, boolean>>

export interface WindowControls {
  minimize: boolean
  close: boolean
}

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

export interface ApplicationDescriptor extends WindowDefinition {
  id: ApplicationId
}

export interface CreateWindowPayload extends WindowDefinition {
  applicationId?: ApplicationId
}

export type WindowMessage =
  | { type: 'create-window'; payload: CreateWindowPayload }
  | { type: 'close-window'; windowId: string }
  | { type: 'minimize-window'; windowId: string }
  | { type: 'focus-window'; windowId: string }

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
