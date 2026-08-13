import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { DesktopApplication } from '@/types/desktop'
import type { Privilege } from '@/registries/commands'

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
  {
    id: 'ascii',
    nameKey: 'applications.ascii.title',
    descriptionKey: 'applications.ascii.description',
    groupKey: 'applicationGroups.creative',
    availability: 'hidden',
  },
  {
    id: 'browser',
    nameKey: 'applications.browser.title',
    descriptionKey: 'applications.browser.description',
    groupKey: 'applicationGroups.system',
    availability: 'available',
  },
]

export const useDesktopStore = defineStore('desktop', () => {
  const isApplicationOverviewOpen = ref(false)
  const availableApplications = computed(() => applications.filter((app) => app.availability === 'available'))
  /** 在 Launchpad 中可见的应用（排除 hidden） */
  const visibleApplications = computed(() => applications.filter((app) => app.availability !== 'hidden'))
  const currentUser = ref('PLAYER')
  /** 当前账号权限等级：LIMITED（玩家）| ADMIN（JDK 触发器管理员） */
  const privilegeClass = ref<Privilege>('LIMITED')
  const accountType = ref<'player' | 'admin' | null>(null)

  // 锁定页状态
  const isLocked = ref(false)
  const lockSessionId = ref<string | null>(null)
  const lockChallengeNonce = ref<string | null>(null)
  const guaranteeAccepted = ref(false)
  const logoutDisabled = ref(false)

  function toggleApplicationOverview() {
    isApplicationOverviewOpen.value = !isApplicationOverviewOpen.value
  }

  function closeApplicationOverview() {
    isApplicationOverviewOpen.value = false
  }

  /** 触发锁定页 */
  function triggerLock(sessionId?: string, nonce?: string) {
    // TODO: 后端就绪后，通过 POST /api/lock/init 获取 sessionId 和 nonce
    lockSessionId.value = sessionId ?? 'lock_sess_dev'
    lockChallengeNonce.value = nonce ?? Math.random().toString(36).slice(2, 10)
    isLocked.value = true

    // 持久化到 sessionStorage，支持刷新恢复
    sessionStorage.setItem(
      'ell_lock_active',
      JSON.stringify({
        sessionId: lockSessionId.value,
        nonce: lockChallengeNonce.value,
      }),
    )
  }

  /** 解锁成功 */
  function resolveLock() {
    isLocked.value = false
    lockSessionId.value = null
    lockChallengeNonce.value = null
    sessionStorage.removeItem('ell_lock_active')
  }

  /** 接受保证 */
  function acceptGuarantee() {
    guaranteeAccepted.value = true
    logoutDisabled.value = true
    isLocked.value = false
    lockSessionId.value = null
    lockChallengeNonce.value = null
    sessionStorage.removeItem('ell_lock_active')
  }

  /** 从 sessionStorage 恢复锁定状态（页面刷新后调用） */
  function rehydrateLock() {
    const saved = sessionStorage.getItem('ell_lock_active')
    if (!saved) return

    try {
      const { sessionId, nonce } = JSON.parse(saved)
      lockSessionId.value = sessionId
      lockChallengeNonce.value = nonce
      isLocked.value = true
    } catch {
      sessionStorage.removeItem('ell_lock_active')
    }
  }

  return {
    applications,
    availableApplications,
    visibleApplications,
    isApplicationOverviewOpen,
    currentUser,
    privilegeClass,
    accountType,
    isLocked,
    lockSessionId,
    lockChallengeNonce,
    guaranteeAccepted,
    logoutDisabled,
    toggleApplicationOverview,
    closeApplicationOverview,
    triggerLock,
    resolveLock,
    acceptGuarantee,
    rehydrateLock,
  }
})
