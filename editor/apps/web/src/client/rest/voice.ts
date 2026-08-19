import {
  VOICE_DEFAULT_MAX_PARTICIPANTS,
  type VoiceChannelListResponse,
  type VoiceChannelResponse,
} from '@ellia/puzzle-schema'

import { jsonBody, request } from '../http'

export function listVoiceChannels(projectId: string): Promise<VoiceChannelListResponse> {
  return request<VoiceChannelListResponse>(
    `/api/projects/${encodeURIComponent(projectId)}/voice/channels`,
  )
}

export function createVoiceChannel(
  projectId: string,
  name: string,
  max_participants = VOICE_DEFAULT_MAX_PARTICIPANTS,
): Promise<VoiceChannelResponse> {
  return request<VoiceChannelResponse>(
    `/api/projects/${encodeURIComponent(projectId)}/voice/channels`,
    {
      method: 'POST',
      body: jsonBody({ name, max_participants }),
    },
  )
}

export function deleteVoiceChannel(
  projectId: string,
  channelId: string,
): Promise<void> {
  return request<void>(
    `/api/projects/${encodeURIComponent(projectId)}/voice/channels/${encodeURIComponent(channelId)}`,
    { method: 'DELETE' },
  )
}
