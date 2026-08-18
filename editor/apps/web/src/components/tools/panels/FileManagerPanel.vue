<script setup lang="ts">
import { onMounted, ref } from 'vue'

import type { ApiFileRecord } from '@ellia/puzzle-schema'

import { deleteFile, downloadFile, listFiles, uploadFile } from '../../../client/rest/files'
import ConfirmDialog from '../../ui/ConfirmDialog.vue'

const files = ref<ApiFileRecord[]>([])
const loading = ref(false)
const uploading = ref(false)
const error = ref<string | null>(null)
const confirmFile = ref<ApiFileRecord | null>(null)
const deleteBusy = ref(false)

onMounted(() => {
  refresh()
})

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

async function onUpload(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  error.value = null
  try {
    await uploadFile(file, file.type || 'application/octet-stream', file.name)
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '上传失败'
  } finally {
    uploading.value = false
    input.value = ''
  }
}

async function onDownload(file: ApiFileRecord): Promise<void> {
  error.value = null
  try {
    const blob = await downloadFile(file.file_id)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = file.original_name ?? file.file_id
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '下载失败'
  }
}

function requestDelete(file: ApiFileRecord): void {
  confirmFile.value = file
}

async function performDelete(): Promise<void> {
  if (!confirmFile.value) return
  const file = confirmFile.value
  confirmFile.value = null
  deleteBusy.value = true
  error.value = null
  try {
    await deleteFile(file.file_id)
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除失败'
  } finally {
    deleteBusy.value = false
  }
}
</script>

<template>
  <div class="file-manager">
    <header class="file-manager__header">
      <h3>文件管理</h3>
      <button class="btn btn--tonal" type="button" :disabled="loading" @click="refresh">
        {{ loading ? '加载中…' : '刷新' }}
      </button>
      <label class="btn btn--primary">
        上传
        <input type="file" hidden :disabled="uploading" @change="onUpload" />
      </label>
    </header>

    <p v-if="error" class="error-text" role="alert">{{ error }}</p>

    <ul class="file-manager__list">
      <li v-for="file in files" :key="file.file_id" class="file-manager__item">
        <div class="file-manager__item-main">
          <span class="file-manager__name" :title="file.file_id">
            {{ file.original_name ?? file.file_id }}
          </span>
          <span class="muted">{{ file.media_type }} · {{ file.size }} bytes</span>
        </div>
        <div class="file-manager__item-actions">
          <button class="btn btn--text btn--small" type="button" @click="onDownload(file)">
            下载
          </button>
          <button class="btn btn--text btn--small" type="button" @click="requestDelete(file)">
            删除
          </button>
        </div>
      </li>
    </ul>

    <p v-if="files.length === 0 && !loading" class="file-manager__empty">暂无文件</p>

    <ConfirmDialog
      v-if="confirmFile"
      :open="Boolean(confirmFile)"
      title="删除文件"
      :message="`确定删除文件 ${confirmFile.original_name ?? confirmFile.file_id}？此操作不可恢复。`"
      confirm-label="删除"
      cancel-label="取消"
      danger
      :busy="deleteBusy"
      @confirm="performDelete"
      @cancel="confirmFile = null"
    />
  </div>
</template>

<style scoped>
.file-manager {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 10px;
  gap: 10px;
  overflow-y: auto;
}

.file-manager__header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.file-manager__header h3 {
  margin: 0;
  font-size: 1rem;
  flex: 1;
}

.file-manager__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
}

.file-manager__item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
  width: 100%;
  padding: 8px;
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  box-sizing: border-box;
}

.file-manager__item-main {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.file-manager__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}

.file-manager__item-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.file-manager__empty {
  color: var(--md-sys-color-on-surface-variant, #49454f);
  text-align: center;
  padding: 24px 0;
}
</style>