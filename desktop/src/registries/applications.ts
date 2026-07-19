import { defineAsyncComponent } from 'vue'
import { Archive, FileText, LockKeyhole, TerminalSquare } from 'lucide-vue-next'

import type { ApplicationDescriptor, ApplicationId } from '@/types/desktop'

export const applicationRegistry: Record<ApplicationId, ApplicationDescriptor> = {
  files: {
    id: 'files',
    title: 'File Explorer',
    icon: FileText,
    component: defineAsyncComponent(() => import('@/components/applications/FileExplorer.vue')),
    defaultWidth: 420,
    defaultHeight: 280,
  },
  archive: {
    id: 'archive',
    title: 'Archive Viewer',
    icon: Archive,
    component: defineAsyncComponent(() => import('@/components/applications/ArchiveViewer.vue')),
    defaultWidth: 460,
    defaultHeight: 300,
  },
  terminal: {
    id: 'terminal',
    title: 'Command Terminal',
    icon: TerminalSquare,
    component: defineAsyncComponent(() => import('@/components/applications/Terminal.vue')),
    defaultWidth: 560,
    defaultHeight: 340,
  },
  sandbox: {
    id: 'sandbox',
    title: 'Sandbox Control',
    icon: LockKeyhole,
    component: defineAsyncComponent(() => import('@/components/applications/SandboxControl.vue')),
    defaultWidth: 400,
    defaultHeight: 260,
  },
}
