import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { DesktopApplication } from '@/types/desktop'

const applications: DesktopApplication[] = [
  {
    id: 'files',
    nameKey: 'applications.files.title',
    descriptionKey: 'applications.files.description',
    groupKey: 'applicationGroups.system',
    availability: 'available',
  },
  {
    id: 'archive',
    nameKey: 'applications.archive.title',
    descriptionKey: 'applications.archive.description',
    groupKey: 'applicationGroups.system',
    availability: 'available',
  },
  {
    id: 'terminal',
    nameKey: 'applications.terminal.title',
    descriptionKey: 'applications.terminal.description',
    groupKey: 'applicationGroups.system',
    availability: 'available',
  },
  {
    id: 'sandbox',
    nameKey: 'applications.sandbox.title',
    descriptionKey: 'applications.sandbox.description',
    groupKey: 'applicationGroups.restricted',
    availability: 'locked',
  },
  {
    id: 'settings',
    nameKey: 'applications.settings.title',
    descriptionKey: 'applications.settings.description',
    groupKey: 'applicationGroups.system',
    availability: 'available',
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
