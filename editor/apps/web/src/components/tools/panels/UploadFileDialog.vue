<script setup lang="ts">
import { ref, watch } from 'vue'

import ModalDialog from '../../ui/ModalDialog.vue'
import TextField from '../../ui/TextField.vue'

const props = defineProps<{
  open: boolean
  file: File | null
  defaultModule: string
}>()

const emit = defineEmits<{
  (e: 'confirm', value: { fileName: string; mediaType: string; module: string }): void
  (e: 'cancel'): void
}>()

const fileName = ref('')
const mediaType = ref('')
const module = ref('')
const error = ref<string | null>(null)

const MEDIA_TYPE_RECOMMENDS = [
  'application/octet-stream',
  'text/plain',
  'text/plain; charset=utf-8',
  'text/html',
  'text/css',
  'application/json',
  'application/javascript',
  'application/xml',
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/svg+xml',
  'application/pdf',
  'application/zip',
  'application/x-tar',
  'audio/mpeg',
  'video/mp4',
]

watch(
  () => props.open,
  (open) => {
    if (!open) return
    error.value = null
    fileName.value = props.file?.name ?? ''
    mediaType.value = props.file?.type || 'application/octet-stream'
    module.value = props.defaultModule || 'main'
  },
)

function confirm(): void {
  const name = fileName.value.trim()
  const type = mediaType.value.trim()
  const mod = module.value.trim()
  if (!name) {
    error.value = '文件名不能为空'
    return
  }
  if (!type) {
    error.value = 'media_type 不能为空'
    return
  }
  if (!mod) {
    error.value = 'module 不能为空'
    return
  }
  emit('confirm', { fileName: name, mediaType: type, module: mod })
}
</script>

<template>
  <ModalDialog
    :open="open"
    title="上传文件"
    confirm-label="上传"
    cancel-label="取消"
    :confirm-disabled="false"
    @confirm="confirm"
    @cancel="emit('cancel')"
  >
    <div class="upload-file-dialog">
      <label class="upload-file-dialog__field">
        <span>文件名</span>
        <TextField v-model="fileName" placeholder="文件名" />
      </label>

      <label class="upload-file-dialog__field">
        <span>media_type</span>
        <TextField v-model="mediaType" :recommends="MEDIA_TYPE_RECOMMENDS" placeholder="media_type" />
      </label>

      <label class="upload-file-dialog__field">
        <span>module</span>
        <TextField v-model="module" placeholder="module" />
      </label>

      <p v-if="error" class="error-text" role="alert">{{ error }}</p>
    </div>
  </ModalDialog>
</template>

<style scoped>
.upload-file-dialog {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.upload-file-dialog__field {
  display: grid;
  gap: 4px;
  font-size: 0.85rem;
}
</style>
