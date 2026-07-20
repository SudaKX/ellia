/**
 * # 应用注册表
 *
 * 所有 FakeOS 应用的集中注册中心。
 * 每个条目包含应用的静态配置（图标、标题、默认尺寸）和异步加载的组件。
 *
 * ## 为什么用 defineAsyncComponent
 *
 * 四个应用（FileExplorer、ArchiveViewer、Terminal、SandboxControl）
 * 在首次打开时才加载对应的 .vue 文件，减少初始包体积。
 * Vite 会将它们拆分为独立的 chunk。
 *
 * DesktopView 在 onMounted 时遍历此注册表，逐一调用
 * `windowService.registerApplication()` 完成注册。
 *
 * ## 与 darksky 分支区别
 *
 * darksky 分支将此注册表内联到 DesktopView.vue 中，
 * 不使用 `defineAsyncComponent`。本分支保留独立的注册表文件
 * 和异步加载，以便后续扩展更多应用时保持代码组织清晰。
 */

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
