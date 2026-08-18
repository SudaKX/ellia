<script setup lang="ts">
import { computed, ref } from 'vue'

import type { EntityRecord } from '@ellia/puzzle-schema'

import { uploadFile } from '../../../client/rest/files'
import { syncClient } from '../../../client/ws'
import { useLocksStore } from '../../../stores/locks'
import LockHint from '../../presence/LockHint.vue'

const props = defineProps<{
  entity: EntityRecord
}>()

const locks = useLocksStore()

const asset = computed(() => props.entity.state as Extract<EntityRecord['state'], { file_id: string }>)
const rootPath = computed(() => `${props.entity.id}@state:`)
const lockedByOther = computed(() => Boolean(locks.holderOf(rootPath.value) && locks.holderOf(rootPath.value)?.holder.id !== undefined))

const busy = ref(false)
const message = ref<string | null>(null)

async function onReplace(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  busy.value = true
  message.value = null
  try {
    const uploaded = await uploadFile(file, file.type || 'application/octet-stream', file.name)
    await syncClient.lock(props.entity.id, rootPath.value)
    await syncClient.patch(props.entity.id, rootPath.value, {
      file_id: uploaded.file_id,
      media_type: uploaded.media_type,
    })
    await syncClient.unlock(props.entity.id, rootPath.value)
  } catch (error) {
    message.value = error instanceof Error ? error.message : '替换文件失败'
  } finally {
    busy.value = false
    input.value = ''
  }
}
</script>

<template>
  <div class="asset-editor">
    <header class="asset-editor__header">
      <h2>{{ entity.resource_id }}</h2>
      <span class="muted">asset · v{{ entity.version }} · r{{ entity.revision }}</span>
    </header>

    <div v-if="lockedByOther" class="asset-editor__lock">
      <LockHint :entity-id="entity.id" :data-path="rootPath" />
    </div>

    <dl class="asset-editor__meta">
      <div>
        <dt>file_id</dt>
        <dd><code>{{ asset.file_id }}</code></dd>
      </div>
      <div>
        <dt>media_type</dt>
        <dd>{{ asset.media_type }}</dd>
      </div>
    </dl>

    <p v-if="message" class="error-text" role="alert">{{ message }}</p>

    <label class="btn btn--primary">
      {{ busy ? '上传中…' : '上传新文件并替换引用' }}
      <input type="file" hidden :disabled="busy || lockedByOther" @change="onReplace" />
    </label>
  </div>
</template>

<style scoped>
.asset-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.asset-editor__header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.asset-editor__meta {
  margin: 0;
  display: grid;
  gap: 6px;
}

.asset-editor__meta dt {
  font-weight: 600;
  font-size: 0.8rem;
}

.asset-editor__meta dd {
  margin: 0;
  font-size: 0.9rem;
}
</style>