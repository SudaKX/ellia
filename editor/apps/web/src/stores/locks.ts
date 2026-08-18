import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import type { AuthorInfo } from '@ellia/puzzle-schema'

import { syncClient } from '../client/ws'

export interface LockInfo {
  entityId: string
  dataPath: string
  holder: AuthorInfo
  acquiredAt?: string
}

export const useLocksStore = defineStore('locks', () => {
  const locks = ref<Record<string, LockInfo>>({})
  const deniedMessages = ref<Array<{ entityId: string; dataPath: string; holder: AuthorInfo }>>([])

  const lockList = computed(() => Object.values(locks.value))

  let subscribed = false

  function ensureSubscriptions(): void {
    if (subscribed) return
    subscribed = true
    syncClient.on('locked', (message) => {
      if (message.user) {
        locks.value = {
          ...locks.value,
          [message.data_path]: {
            entityId: message.entity_id,
            dataPath: message.data_path,
            holder: message.user,
          },
        }
      }
    })
    syncClient.on('unlocked', (message) => {
      const next = { ...locks.value }
      delete next[message.data_path]
      locks.value = next
    })
    syncClient.on('lock_denied', (message) => {
      deniedMessages.value = [
        ...deniedMessages.value,
        { entityId: message.entity_id, dataPath: message.data_path, holder: message.holder },
      ]
    })
    syncClient.on('locks', (message) => {
      const next: Record<string, LockInfo> = {}
      for (const lock of message.locks) {
        const entityId = lock.data_path.split('@')[0] ?? ''
        next[lock.data_path] = {
          entityId,
          dataPath: lock.data_path,
          holder: lock.holder,
        }
      }
      locks.value = next
    })
  }

  function isLocked(entityId: string, dataPath: string): boolean {
    return Boolean(locks.value[dataPath] && locks.value[dataPath]?.entityId === entityId)
  }

  function holderOf(dataPath: string): LockInfo | undefined {
    return locks.value[dataPath]
  }

  function clearDenied(): void {
    deniedMessages.value = []
  }

  function clear(): void {
    locks.value = {}
    deniedMessages.value = []
  }

  return {
    locks,
    deniedMessages,
    lockList,
    ensureSubscriptions,
    isLocked,
    holderOf,
    clearDenied,
    clear,
  }
})