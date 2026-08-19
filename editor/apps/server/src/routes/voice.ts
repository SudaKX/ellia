import { Router } from 'express'

import {
  VOICE_DEFAULT_MAX_PARTICIPANTS,
  type VoiceChannelListResponse,
  type VoiceChannelResponse,
} from '@ellia/puzzle-schema'

import { requireAuth } from '../auth/middleware.js'
import { loadConfig } from '../config.js'
import { requireProject } from '../voice/channels.js'
import { getVoiceManager } from '../voice/manager.js'

export const voiceRouter = Router({ mergeParams: true })

voiceRouter.use(requireAuth)

voiceRouter.get('/channels', (req, res) => {
  const projectId = String((req.params as { projectId?: string }).projectId ?? '')
  requireProject(projectId)
  const channels = getVoiceManager(loadConfig()).listChannelDtos(projectId)
  const body: VoiceChannelListResponse = { channels }
  res.json(body)
})

voiceRouter.post('/channels', (req, res) => {
  const projectId = String((req.params as { projectId?: string }).projectId ?? '')
  const body = (req.body ?? {}) as Record<string, unknown>
  const name = typeof body.name === 'string' ? body.name : ''
  const user = res.locals.user as { id: string }
  const maxParticipants =
    typeof body.max_participants === 'number'
      ? body.max_participants
      : VOICE_DEFAULT_MAX_PARTICIPANTS
  const channel = getVoiceManager(loadConfig()).createChannel(
    projectId,
    name,
    user.id,
    maxParticipants,
  )
  const response: VoiceChannelResponse = { channel }
  res.status(201).json(response)
})

voiceRouter.delete('/channels/:channelId', async (req, res) => {
  const projectId = String((req.params as { projectId?: string }).projectId ?? '')
  const channelId = String((req.params as { channelId?: string }).channelId ?? '')
  requireProject(projectId)
  await getVoiceManager(loadConfig()).deleteChannel(projectId, channelId)
  res.status(204).end()
})
