import { defineAsyncComponent } from 'vue'
import { Archive, FileText, LockKeyhole, Settings, TerminalSquare } from 'lucide-vue-next'

import type { ApplicationDescriptor, ApplicationId } from '@/types/desktop'

export const applicationRegistry: Record<ApplicationId, ApplicationDescriptor> = {
  files: {
    id: 'files',
    titleKey: 'applications.files.title',
    icon: FileText,
    component: defineAsyncComponent(() => import('@/components/applications/FileExplorer.vue')),
    defaultWidth: 420,
    defaultHeight: 280,
  },
  archive: {
    id: 'archive',
    titleKey: 'applications.archive.title',
    icon: Archive,
    component: defineAsyncComponent(() => import('@/components/applications/ArchiveViewer.vue')),
    defaultWidth: 460,
    defaultHeight: 300,
  },
  terminal: {
    id: 'terminal',
    titleKey: 'applications.terminal.title',
    icon: TerminalSquare,
    component: defineAsyncComponent(() => import('@/components/applications/Terminal.vue')),
    defaultWidth: 560,
    defaultHeight: 340,
  },
  sandbox: {
    id: 'sandbox',
    titleKey: 'applications.sandbox.title',
    icon: LockKeyhole,
    component: defineAsyncComponent(() => import('@/components/applications/SandboxControl.vue')),
    defaultWidth: 400,
    defaultHeight: 260,
  },
  settings: {
    id: 'settings',
    titleKey: 'applications.settings.title',
    icon: Settings,
    component: defineAsyncComponent(() => import('@/components/applications/Settings.vue')),
    defaultWidth: 440,
    defaultHeight: 300,
  },
}
