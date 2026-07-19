import type { Component } from 'vue'

export type ApplicationId = 'files' | 'archive' | 'terminal' | 'sandbox'

export interface DesktopApplication {
  id: ApplicationId
  name: string
  description: string
  group: string
  availability: 'available' | 'locked'
}

export interface ApplicationDescriptor {
  id: ApplicationId
  title: string
  icon: Component
  component: Component
  defaultWidth: number
  defaultHeight: number
}

export interface WindowInstance {
  id: string
  applicationId: ApplicationId
  title: string
  icon: Component
  component: Component
  x: number
  y: number
  width: number
  height: number
  zIndex: number
  isMinimized: boolean
}
