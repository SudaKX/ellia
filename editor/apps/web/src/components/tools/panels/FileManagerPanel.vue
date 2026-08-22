<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type { ApiFileRecord } from '@ellia/puzzle-schema'

import { deleteFile, downloadFile, uploadFile } from '../../../client/rest/files'
import { useFilesStore } from '../../../stores/files'
import ConfirmDialog from '../../ui/ConfirmDialog.vue'
import TextField from '../../ui/TextField.vue'
import UploadFileDialog from './UploadFileDialog.vue'

const filesStore = useFilesStore()

const loading = computed(() => filesStore.loading)
const files = computed(() => filesStore.files)
const error = ref<string | null>(null)
const confirmFile = ref<ApiFileRecord | null>(null)
const deleteBusy = ref(false)

const searchQuery = ref('')
const filteredFiles = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return files.value
  return files.value.filter(
    (file) =>
      (file.original_name ?? '').toLowerCase().includes(query) ||
      file.file_id.toLowerCase().includes(query),
  )
})

const selectedFile = ref<ApiFileRecord | null>(null)

const uploadInput = ref<HTMLInputElement | null>(null)
const pendingUpload = ref<File | null>(null)
const uploadOpen = ref(false)
const uploadBusy = ref(false)

onMounted(() => {
  void refresh()
})

async function refresh(): Promise<void> {
  error.value = null
  await filesStore.refresh()
  if (filesStore.error) error.value = filesStore.error
}

function onUploadPick(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  pendingUpload.value = file
  uploadOpen.value = true
  input.value = ''
}

async function confirmUpload(value: { fileName: string; mediaType: string; module: string }): Promise<void> {
  if (!pendingUpload.value) return
  uploadBusy.value = true
  error.value = null
  try {
    const uploaded = await uploadFile(
      pendingUpload.value,
      value.mediaType,
      value.fileName,
      value.module,
    )
    uploadOpen.value = false
    pendingUpload.value = null
    await refresh()
    selectedFile.value = uploaded
  } catch (err) {
    error.value = err instanceof Error ? err.message : '上传失败'
  } finally {
    uploadBusy.value = false
  }
}

function cancelUpload(): void {
  uploadOpen.value = false
  pendingUpload.value = null
}

function toggleSelect(file: ApiFileRecord): void {
  selectedFile.value = selectedFile.value?.file_id === file.file_id ? null : file
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
    if (selectedFile.value?.file_id === file.file_id) selectedFile.value = null
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
      <div class="file-manager__header-row">
        <h3>文件管理</h3>
        <button class="btn btn--tonal" type="button" :disabled="loading" @click="refresh">
          {{ loading ? '加载中…' : '刷新' }}
        </button>
        <button class="btn btn--primary" type="button" :disabled="loading || uploadBusy" @click="uploadInput?.click()">
          上传
        </button>
      </div>
      <div class="file-manager__header-search">
        <TextField v-model="searchQuery" placeholder="搜索文件名称" />
      </div>
    </header>

    <p v-if="error" class="error-text" role="alert">{{ error }}</p>

    <div class="file-manager__content">
      <ul class="file-manager__list">
        <li
          v-for="file in filteredFiles"
          :key="file.file_id"
          class="file-manager__item"
          :class="{ 'file-manager__item--selected': selectedFile?.file_id === file.file_id }"
          @click="toggleSelect(file)"
        >
          <div class="file-manager__item-main">
            <span class="file-manager__name" :title="file.file_id">
              {{ file.original_name ?? file.file_id }}
            </span>
            <span class="muted">{{ file.media_type }} · {{ file.size }} bytes</span>
          </div>
          <div class="file-manager__item-actions" @click.stop>
            <button class="btn btn--text btn--small" type="button" @click="onDownload(file)">
              下载
            </button>
            <button class="btn btn--text btn--small" type="button" @click="requestDelete(file)">
              删除
            </button>
          </div>
        </li>
      </ul>

      <p v-if="filteredFiles.length === 0 && !loading" class="file-manager__empty">
        {{ searchQuery ? '没有匹配的文件' : '暂无文件' }}
      </p>
    </div>

    <section class="file-manager__details">
      <h4>选中文件详情</h4>
      <template v-if="selectedFile">
        <dl class="file-manager__details-grid">
          <div><dt>文件名</dt><dd>{{ selectedFile.original_name ?? '—' }}</dd></div>
          <div><dt>media_type</dt><dd>{{ selectedFile.media_type }}</dd></div>
          <div><dt>module</dt><dd>{{ selectedFile.module ?? '—' }}</dd></div>
          <div><dt>大小</dt><dd>{{ selectedFile.size }} bytes</dd></div>
          <div><dt>sha256</dt><dd><code>{{ selectedFile.sha256 }}</code></dd></div>
          <div><dt>上传者</dt><dd>{{ selectedFile.uploaded_by }}</dd></div>
          <div><dt>创建时间</dt><dd>{{ selectedFile.created_at }}</dd></div>
          <div><dt>file_id</dt><dd><code>{{ selectedFile.file_id }}</code></dd></div>
        </dl>
      </template>
      <p v-else class="file-manager__details-empty">选择一个文件查看详情</p>
    </section>

    <input ref="uploadInput" type="file" hidden @change="onUploadPick" />

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

    <UploadFileDialog
      :open="uploadOpen"
      :file="pendingUpload"
      default-module="main"
      @confirm="confirmUpload"
      @cancel="cancelUpload"
    />
  </div>
</template>

<style scoped>
.file-manager {
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;
  padding: 10px;
  gap: 8px;
  overflow: hidden;
}

.file-manager__header {
  flex: none;
  display: grid;
  gap: 8px;
}

.file-manager__header-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.file-manager__header-row h3 {
  margin: 0;
  font-size: 1rem;
  flex: 1;
}

.file-manager__header-search {
  display: grid;
}

.file-manager__content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
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
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.file-manager__item:hover {
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.file-manager__item--selected {
  border-color: var(--md-sys-color-primary, #6750a4);
  background: var(--md-sys-color-primary-container, #eaddff);
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

.file-manager__details {
  flex: none;
  min-height: 64px;
  padding: 8px 10px;
  border-top: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  background: var(--md-sys-color-surface-container-low, #f7f2fa);
  display: grid;
  gap: 6px;
}

.file-manager__details h4 {
  margin: 0;
  font-size: 0.9rem;
}

.file-manager__details-grid {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 6px 12px;
}

.file-manager__details-grid dt {
  font-size: 0.72rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.file-manager__details-grid dd {
  margin: 0;
  font-size: 0.8rem;
  overflow-wrap: anywhere;
}

.file-manager__details-empty {
  margin: 0;
  color: var(--md-sys-color-on-surface-variant, #49454f);
  font-size: 0.8rem;
}
</style>
