export type ApplicationId = 'files' | 'archive' | 'terminal' | 'sandbox'

export interface DesktopApplication {
  id: ApplicationId
  name: string
  description: string
  group: string
  availability: 'available' | 'locked'
}
