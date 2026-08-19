// @ellia/puzzle-schema — 语音聊天共享类型
// 频道元数据持久化在 SQLite；在线参与者与 WebRTC 连接仅存内存。

export const VOICE_DEFAULT_MAX_PARTICIPANTS = 8

/** voice_channels 表行（SQLite 持久化） */
export interface VoiceChannelRecord {
  id: string
  project_id: string
  name: string
  max_participants: number
  created_by: string
  created_at: string
  updated_at: string
}

/** 返回给前端的频道 DTO；participant_count 来自内存实时状态 */
export interface VoiceChannelDto {
  id: string
  name: string
  max_participants: number
  participant_count: number
}

export interface VoiceParticipantDto {
  id: string
  username: string
  muted: boolean
}

export interface VoiceChannelListResponse {
  channels: VoiceChannelDto[]
}

export interface VoiceChannelResponse {
  channel: VoiceChannelDto
}
