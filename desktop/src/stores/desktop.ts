import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { DesktopApplication } from '@/types/desktop'

const applications: DesktopApplication[] = [
  {
    id: 'files',
    name: 'File Explorer',
    description: 'Inspect authorized system volumes.',
    group: 'System',
    availability: 'available',
  },
  {
    id: 'archive',
    name: 'Archive Viewer',
    description: 'Read recovered session material.',
    group: 'System',
    availability: 'available',
  },
  {
    id: 'terminal',
    name: 'Command Terminal',
    description: 'Execute local console utilities.',
    group: 'System',
    availability: 'available',
  },
  {
    id: 'sandbox',
    name: 'Sandbox Control',
    description: 'Restricted administrative environment.',
    group: 'Restricted',
    availability: 'locked',
  },
]

export const useDesktopStore = defineStore('desktop', () => {
  const isApplicationOverviewOpen = ref(false)
  const availableApplications = computed(() => applications.filter((app) => app.availability === 'available'))
  const currentUser = ref('PLAYER')
  const privilegeClass = ref('LIMITED')

  function toggleApplicationOverview() {
    isApplicationOverviewOpen.value = !isApplicationOverviewOpen.value
  }

  function closeApplicationOverview() {
    isApplicationOverviewOpen.value = false
  }

  return {
    applications,
    availableApplications,
    isApplicationOverviewOpen,
    currentUser,
    privilegeClass,
    toggleApplicationOverview,
    closeApplicationOverview,
  }
})
