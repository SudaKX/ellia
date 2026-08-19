import type { VoiceChannelDto, VoiceParticipantDto } from '@ellia/puzzle-schema'

export type VoiceConnectionStatus = 'idle' | 'connecting' | 'connected' | 'error'

export interface VoiceServiceEvents {
  status: (status: VoiceConnectionStatus, error?: string) => void
  channels: (channels: VoiceChannelDto[]) => void
  joined: (channelId: string, participants: VoiceParticipantDto[]) => void
  left: (channelId: string) => void
  'peer.joined': (participant: VoiceParticipantDto) => void
  'peer.left': (participant: VoiceParticipantDto) => void
  participants: (channelId: string, participants: VoiceParticipantDto[]) => void
  'remote-track': (participantId: string, stream: MediaStream) => void
  'remote-track-ended': (participantId: string) => void
  speaker: (userId: string, speaking: boolean) => void
}

export type VoiceServiceEvent = keyof VoiceServiceEvents

export interface VoiceService {
  readonly status: VoiceConnectionStatus
  connect(projectId: string): Promise<void>
  disconnect(): void
  listChannels(): Promise<VoiceChannelDto[]>
  createChannel(name: string, maxParticipants?: number): Promise<VoiceChannelDto>
  deleteChannel(channelId: string): Promise<void>
  joinChannel(channelId: string): Promise<void>
  leaveChannel(): Promise<void>
  setMuted(muted: boolean): void
  setNoiseSuppression(enabled: boolean): Promise<void>
  setMicVolume(volume: number): void
  setSilenceThreshold(threshold: number): void
  on<K extends VoiceServiceEvent>(event: K, handler: VoiceServiceEvents[K]): () => void
}
