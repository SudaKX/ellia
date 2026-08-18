import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import type { PresenceUser } from '@ellia/puzzle-schema'

import { syncClient } from '../client/ws'

export const usePresenceStore = defineStore('presence', () => {
  const users = ref<PresenceUser[]>([])
  const lastUpdatedAt = ref<number | null>(null)

  let subscribed = false

  const usersByEntity = computed<Record<string, PresenceUser[]>>(() => {
    const result: Record<string, PresenceUser[]> = {}
    for (const user of users.value) {
      if (!user.entity_id) continue
      const list = result[user.entity_id] ?? []
      list.push(user)
      result[user.entity_id] = list
    }
    return result
  })

  function ensureSubscriptions(): void {
    if (subscribed) return
    subscribed = true
    syncClient.on('presence', (message) => {
      users.value = message.users
      lastUpdatedAt.value = Date.now()
    })
  }

  function userAtPath(entityId: string, dataPath: string): PresenceUser[] {
    return users.value.filter(
      (user) => user.entity_id === entityId && user.data_path === dataPath,
    )
  }

  function clear(): void {
    users.value = []
    lastUpdatedAt.value = null
  }

  return {
    users,
    lastUpdatedAt,
    usersByEntity,
    ensureSubscriptions,
    userAtPath,
    clear,
  }
})