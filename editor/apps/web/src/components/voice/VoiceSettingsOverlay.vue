<script setup lang="ts">
import { ref } from 'vue'

import type { VoiceChannelDto } from '@ellia/puzzle-schema'

import { useVoiceStore } from '../../stores/voice'
import ConfirmDialog from '../ui/ConfirmDialog.vue'
import TextField from '../ui/TextField.vue'

const voice = useVoiceStore()

const newChannelName = ref('')
const busy = ref(false)
const error = ref<string | null>(null)
const deleteTarget = ref<VoiceChannelDto | null>(null)
const deleteBusy = ref(false)

function askDeleteChannel(channel: VoiceChannelDto): void {
  deleteTarget.value = channel
}

function cancelDeleteChannel(): void {
  if (deleteBusy.value) return
  deleteTarget.value = null
}

async function confirmDeleteChannel(): Promise<void> {
  const target = deleteTarget.value
  if (!target) return
  deleteBusy.value = true
  error.value = null
  try {
    await voice.deleteChannel(target.id)
    deleteTarget.value = null
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除频道失败'
  } finally {
    deleteBusy.value = false
  }
}

async function createChannel(): Promise<void> {
  const name = newChannelName.value.trim()
  if (!name) return
  busy.value = true
  error.value = null
  try {
    await voice.createChannel(name)
    newChannelName.value = ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : '创建频道失败'
  } finally {
    busy.value = false
  }
}

async function joinChannel(channelId: string): Promise<void> {
  busy.value = true
  error.value = null
  try {
    await voice.joinChannel(channelId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加入频道失败'
  } finally {
    busy.value = false
  }
}

async function leaveChannel(): Promise<void> {
  busy.value = true
  try {
    await voice.leaveChannel()
  } finally {
    busy.value = false
  }
}

function isFull(channel: { participant_count: number; max_participants: number }): boolean {
  return channel.participant_count >= channel.max_participants
}
</script>

<template>
  <Teleport to="body">
    <div v-if="voice.settingsOpen" class="voice-overlay" @click.self="voice.closeSettings()">
      <div class="voice-overlay__dialog" role="dialog" aria-modal="true" aria-label="语音设置">
        <header class="voice-overlay__header">
          <h3>语音设置</h3>
          <button class="voice-overlay__close" type="button" aria-label="关闭" @click="voice.closeSettings()">
            ×
          </button>
        </header>

        <div class="voice-overlay__body">
          <p class="voice-overlay__status">
            <span
              class="voice-status-dot"
              :class="`voice-status-dot--${voice.status}`"
            />
            {{ voice.status === 'connected' ? '语音服务已连接' : voice.status === 'connecting' ? '连接中…' : '未连接' }}
          </p>
          <p v-if="voice.error || error" class="error-text" role="alert">
            {{ error ?? voice.error }}
          </p>

          <section class="voice-section">
            <h4>音频设置</h4>
            <label class="voice-setting">
              <span>浏览器降噪</span>
              <input
                type="checkbox"
                :checked="voice.noiseSuppression"
                @change="voice.setNoiseSuppression(($event.target as HTMLInputElement).checked)"
              />
            </label>
            <label class="voice-setting">
              <span>麦克风音量：{{ Math.round(voice.micVolume * 100) }}%</span>
              <input
                type="range"
                min="0"
                max="3"
                step="0.01"
                :value="voice.micVolume"
                @input="voice.setMicVolume(Number(($event.target as HTMLInputElement).value))"
              />
            </label>
            <label class="voice-setting">
              <span>扬声器音量：{{ Math.round(voice.speakerVolume * 100) }}%</span>
              <input
                type="range"
                min="0"
                max="3"
                step="0.01"
                :value="voice.speakerVolume"
                @input="voice.setSpeakerVolume(Number(($event.target as HTMLInputElement).value))"
              />
            </label>
            <label class="voice-setting">
              <span>静音阈值：{{ Math.round(voice.silenceThreshold * 10000) / 100 }}</span>
              <input
                type="range"
                min="0"
                max="0.03"
                step="0.0001"
                :value="voice.silenceThreshold"
                @input="voice.setSilenceThreshold(Number(($event.target as HTMLInputElement).value))"
              />
            </label>
          </section>

          <section class="voice-section">
            <h4>频道</h4>
            <div v-if="voice.channels.length === 0" class="muted">还没有频道，创建第一个吧。</div>
            <ul class="voice-channel-list">
              <li v-for="channel in voice.channels" :key="channel.id" class="voice-channel">
                <div class="voice-channel__info">
                  <span class="voice-channel__name">{{ channel.name }}</span>
                  <span class="voice-channel__count">{{ channel.participant_count }}/{{ channel.max_participants }}</span>
                </div>
                <div class="voice-channel__actions">
                  <button
                    class="btn btn--small btn--danger"
                    type="button"
                    :disabled="busy || deleteBusy"
                    @click="askDeleteChannel(channel)"
                  >
                    删除
                  </button>
                  <button
                    v-if="voice.currentChannelId === channel.id"
                    class="btn btn--text"
                    type="button"
                    disabled
                  >
                    已加入
                  </button>
                  <button
                    v-else
                    class="btn btn--primary"
                    type="button"
                    :disabled="busy || isFull(channel)"
                    @click="joinChannel(channel.id)"
                  >
                    {{ isFull(channel) ? '已满' : '加入' }}
                  </button>
                </div>
              </li>
            </ul>
            <form class="voice-create" @submit.prevent="createChannel">
              <TextField v-model="newChannelName" placeholder="新频道名称（最多 40 字）" />
              <button class="btn btn--primary" type="submit" :disabled="busy || !newChannelName.trim()">
                创建频道
              </button>
            </form>
          </section>

          <section v-if="voice.currentChannelId" class="voice-section">
            <h4>当前频道成员</h4>
            <ul class="voice-member-list">
              <li v-for="participant in voice.participants" :key="participant.id" class="voice-member">
                <span class="voice-member__name">
                  <span
                    class="voice-member__speaking-dot"
                    :class="{ 'voice-member__speaking-dot--active': voice.speakers[participant.id] }"
                  />
                  {{ participant.username }}
                </span>
                <span v-if="participant.muted" class="voice-member__muted">已静音</span>
              </li>
            </ul>
            <div class="voice-actions">
              <button class="btn" type="button" :disabled="busy" @click="voice.toggleMute()">
                {{ voice.muted ? '取消静音' : '静音' }}
              </button>
              <button class="btn btn--danger" type="button" :disabled="busy" @click="leaveChannel()">
                离开频道
              </button>
            </div>
          </section>
        </div>

        <footer class="voice-overlay__footer">
          <button class="btn btn--text" type="button" @click="voice.closeSettings()">关闭</button>
        </footer>
      </div>
    </div>
  </Teleport>

  <ConfirmDialog
    :open="!!deleteTarget"
    title="删除频道"
    :message="deleteTarget ? `确定删除频道“${deleteTarget.name}”？频道内成员会被移出。` : ''"
    confirm-label="删除"
    cancel-label="取消"
    danger
    :busy="deleteBusy"
    @confirm="confirmDeleteChannel"
    @cancel="cancelDeleteChannel"
  />
</template>

<style scoped>
.voice-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  background: rgb(0 0 0 / 0.4);
  padding: 1rem;
}

.voice-overlay__dialog {
  width: min(460px, 100%);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  background: var(--md-sys-color-surface-container-high, #ece6f0);
  color: var(--md-sys-color-on-surface, #1d1b20);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgb(0 0 0 / 0.25);
  overflow: hidden;
}

.voice-overlay__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
}

.voice-overlay__header h3 {
  margin: 0;
  font-size: 1rem;
}

.voice-overlay__close {
  border: none;
  background: transparent;
  font-size: 1.25rem;
  cursor: pointer;
  color: var(--md-sys-color-on-surface, #1d1b20);
}

.voice-overlay__body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: grid;
  gap: 16px;
}

.voice-overlay__status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 0.85rem;
}

.voice-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--md-sys-color-outline, #79747e);
}

.voice-status-dot--connected {
  background: #4caf50;
}

.voice-status-dot--connecting {
  background: #ffb300;
}

.voice-status-dot--error {
  background: #f44336;
}

.voice-section h4 {
  margin: 0 0 8px;
  font-size: 0.9rem;
}

.voice-setting {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 0;
  font-size: 0.85rem;
}

.voice-setting input[type='range'] {
  flex: 1 1 auto;
  min-width: 0;
  max-width: 220px;
  -webkit-appearance: none;
  appearance: none;
  height: 4px;
  border-radius: 999px;
  background: var(--md-sys-color-surface-container-highest, #e6e0e9);
  outline: none;
}

.voice-setting input[type='range']::-webkit-slider-runnable-track {
  height: 4px;
  border-radius: 999px;
  background: var(--md-sys-color-surface-container-highest, #e6e0e9);
}

.voice-setting input[type='range']::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  margin-top: -6px;
  border-radius: 50%;
  background: var(--md-sys-color-primary, #6750a4);
  border: 2px solid var(--md-sys-color-on-primary, #ffffff);
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.3);
  cursor: pointer;
}

.voice-setting input[type='range']::-moz-range-track {
  height: 4px;
  border-radius: 999px;
  background: var(--md-sys-color-surface-container-highest, #e6e0e9);
}

.voice-setting input[type='range']::-moz-range-thumb {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--md-sys-color-primary, #6750a4);
  border: 2px solid var(--md-sys-color-on-primary, #ffffff);
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.3);
  cursor: pointer;
}

.voice-member__name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.voice-member__speaking-dot {
  flex: none;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #9e9e9e;
}

.voice-member__speaking-dot--active {
  background: #4caf50;
}

.voice-channel-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 6px;
}

.voice-member-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.voice-channel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--md-sys-color-surface-container, #f3edf7);
}

.voice-channel__info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.voice-channel__actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: none;
}

.voice-channel__actions .btn {
  flex: none;
  white-space: nowrap;
}

.voice-channel__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.voice-channel__count {
  font-size: 0.75rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.voice-create {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.voice-create .btn {
  flex: none;
  white-space: nowrap;
}

.voice-create :deep(.text-field) {
  flex: 1;
}

.voice-member {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--md-sys-color-surface-container, #f3edf7);
  font-size: 0.85rem;
}

.voice-member__muted {
  font-size: 0.72rem;
  color: var(--md-sys-color-on-surface-variant, #49454f);
}

.voice-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.voice-overlay__footer {
  display: flex;
  justify-content: flex-end;
  padding: 10px 16px;
  border-top: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
}
</style>
