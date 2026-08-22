import { ref } from 'vue'
import { defineStore } from 'pinia'

import type { ApiFileRecord } from '@ellia/puzzle-schema'

import { listFiles } from '../client/rest/files'

export const useFilesStore = defineStore('files', () => {
  const files = ref<ApiFileRecord[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await listFiles()
      files.value = response.files
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载文件列表失败'
    } finally {
      loading.value = false
    }
  }

  function findById(fileId: string): ApiFileRecord | null {
    return files.value.find((file) => file.file_id === fileId) ?? null
  }

  return {
    files,
    loading,
    error,
    refresh,
    findById,
  }
})
