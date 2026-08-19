import { defineStore } from 'pinia'
import { ref } from 'vue'

import type { VoiceChannelDto, VoiceParticipantDto } from '@ellia/puzzle-schema'

import { voiceService, type VoiceConnectionStatus } from '../services/voice'

export const useVoiceStore = defineStore('voice', () => {
  const status = ref<VoiceConnectionStatus>(voiceService.status)
  const error = ref<string | null>(null)
  const channels = ref<VoiceChannelDto[]>([])
  const currentChannelId = ref<string | null>(null)
  const participants = ref<VoiceParticipantDto[]>([])
  const muted = ref(false)
  const settingsOpen = ref(false)
  const remoteStreams = ref<Record<string, MediaStream>>({})
  const noiseSuppression = ref(false)
  const micVolume = ref(1)
  const speakerVolume = ref(1)
  const silenceThreshold = ref(0.1)
  const speakers = ref<Record<string, boolean>>({})

  let subscribed = false
  let projectId: string | null = null
  const unsubscribes: Array<() => void> = []

  function ensureSubscriptions(): void {
    if (subscribed) return
    subscribed = true
    unsubscribes.push(
      voiceService.on('status', (nextStatus, nextError) => {
        status.value = nextStatus
        error.value = nextError ?? null
      }),
    )
    unsubscribes.push(
      voiceService.on('channels', (nextChannels) => {
        channels.value = nextChannels
      }),
    )
    unsubscribes.push(
      voiceService.on('joined', (channelId, nextParticipants) => {
        currentChannelId.value = channelId
        participants.value = nextParticipants
        if (channelId) muted.value = false
      }),
    )
    unsubscribes.push(
      voiceService.on('left', (channelId) => {
        if (channelId === currentChannelId.value) {
          currentChannelId.value = null
          participants.value = []
          muted.value = false
          remoteStreams.value = {}
          speakers.value = {}
        }
      }),
    )
    unsubscribes.push(
      voiceService.on('participants', (_channelId, nextParticipants) => {
        participants.value = nextParticipants
      }),
    )
    unsubscribes.push(
      voiceService.on('peer.joined', (participant) => {
        if (participants.value.some((item) => item.id === participant.id)) return
        participants.value = [...participants.value, participant]
      }),
    )
    unsubscribes.push(
      voiceService.on('peer.left', (participant) => {
        participants.value = participants.value.filter((item) => item.id !== participant.id)
      }),
    )
    unsubscribes.push(
      voiceService.on('remote-track', (participantId, stream) => {
        remoteStreams.value = { ...remoteStreams.value, [participantId]: stream }
      }),
    )
    unsubscribes.push(
      voiceService.on('remote-track-ended', (participantId) => {
        const next = { ...remoteStreams.value }
        delete next[participantId]
        remoteStreams.value = next
      }),
    )
    unsubscribes.push(
      voiceService.on('speaker', (userId, speaking) => {
        speakers.value = { ...speakers.value, [userId]: speaking }
      }),
    )
  }

  function clearSubscriptions(): void {
    for (const unsubscribe of unsubscribes.splice(0)) unsubscribe()
    subscribed = false
  }

  async function init(nextProjectId: string): Promise<void> {
    ensureSubscriptions()
    projectId = nextProjectId
    await voiceService.connect(nextProjectId)
    await refreshChannels()
  }

  async function dispose(): Promise<void> {
    voiceService.disconnect()
    currentChannelId.value = null
    participants.value = []
    muted.value = false
    remoteStreams.value = {}
    speakers.value = {}
    channels.value = []
    settingsOpen.value = false
    error.value = null
    status.value = voiceService.status
    projectId = null
  }

  async function refreshChannels(): Promise<void> {
    const next = await voiceService.listChannels()
    channels.value = next
  }

  async function createChannel(name: string): Promise<VoiceChannelDto> {
    const channel = await voiceService.createChannel(name)
    await refreshChannels()
    return channel
  }

  async function deleteChannel(channelId: string): Promise<void> {
    await voiceService.deleteChannel(channelId)
    if (currentChannelId.value === channelId) {
      currentChannelId.value = null
      participants.value = []
      remoteStreams.value = {}
      speakers.value = {}
    }
    await refreshChannels()
  }

  async function joinChannel(channelId: string): Promise<void> {
    if (currentChannelId.value === channelId) return
    if (currentChannelId.value) await voiceService.leaveChannel()
    await voiceService.joinChannel(channelId)
  }

  async function leaveChannel(): Promise<void> {
    await voiceService.leaveChannel()
    currentChannelId.value = null
    participants.value = []
    remoteStreams.value = {}
    speakers.value = {}
  }

  function toggleMute(): void {
    muted.value = !muted.value
    voiceService.setMuted(muted.value)
  }

  function setNoiseSuppression(enabled: boolean): void {
    noiseSuppression.value = enabled
    void voiceService.setNoiseSuppression(enabled)
  }

  function setMicVolume(volume: number): void {
    micVolume.value = volume
    voiceService.setMicVolume(volume)
  }

  function setSpeakerVolume(volume: number): void {
    speakerVolume.value = volume
  }

  function setSilenceThreshold(threshold: number): void {
    silenceThreshold.value = threshold
    voiceService.setSilenceThreshold(threshold)
  }

  function openSettings(): void {
    settingsOpen.value = true
    void refreshChannels()
  }

  function closeSettings(): void {
    settingsOpen.value = false
  }

  return {
    status,
    error,
    channels,
    currentChannelId,
    participants,
    muted,
    settingsOpen,
    remoteStreams,
    noiseSuppression,
    micVolume,
    speakerVolume,
    silenceThreshold,
    speakers,
    init,
    dispose,
    refreshChannels,
    createChannel,
    deleteChannel,
    joinChannel,
    leaveChannel,
    toggleMute,
    setNoiseSuppression,
    setMicVolume,
    setSpeakerVolume,
    setSilenceThreshold,
    openSettings,
    closeSettings,
  }
})
