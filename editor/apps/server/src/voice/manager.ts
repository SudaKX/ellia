import { randomUUID } from 'node:crypto'

import {
  VOICE_DEFAULT_MAX_PARTICIPANTS,
  type VoiceChannelDto,
  type VoiceChannelRecord,
  type VoiceParticipantDto,
} from '@ellia/puzzle-schema'
import { WebSocket, type WebSocket as WsSocket } from 'ws'
import type * as mediasoup from 'mediasoup'

import type { ServerConfig } from '../config.js'
import { ApiError } from '../errors.js'
import {
  createVoiceChannel,
  deleteVoiceChannel,
  findVoiceChannelById,
  listVoiceChannels,
} from './channels.js'
import {
  MediasoupService,
  type Consumer,
  type Producer,
  type WebRtcTransport,
} from './mediasoup.js'

export interface VoiceServerMessage {
  type: string
  [key: string]: unknown
}

type RtpCapabilities = mediasoup.types.RtpCapabilities
type DtlsParameters = mediasoup.types.DtlsParameters
type MediaKind = mediasoup.types.MediaKind
type RtpParameters = mediasoup.types.RtpParameters

interface VoiceParticipant {
  connectionId: string
  projectId: string
  userId: string
  username: string
  channelId: string | null
  muted: boolean
  ws: WsSocket
  rtpCapabilities?: RtpCapabilities
  sendTransport?: WebRtcTransport
  recvTransport?: WebRtcTransport
  producer?: Producer
  /** 当前连接收到的 consumer，按 producerId 索引 */
  consumers: Map<string, Consumer>
}

interface ChannelState {
  record: VoiceChannelRecord
  participants: Map<string, VoiceParticipant> // connectionId -> participant
}

export class VoiceManager {
  private readonly channels = new Map<string, Map<string, ChannelState>>() // projectId -> channelId -> state
  private readonly participants = new Map<string, VoiceParticipant>() // connectionId -> participant
  private readonly producerOwners = new Map<string, string>() // producerId -> connectionId
  private readonly producerUserIds = new Map<string, string>() // producerId -> userId
  private readonly consumerOwners = new Map<string, string>() // consumerId -> connectionId
  private readonly mediasoupService: MediasoupService
  private operationQueue: Promise<unknown> = Promise.resolve()

  constructor(config: ServerConfig) {
    this.mediasoupService = new MediasoupService(config)
    this.mediasoupService.onWorkerDied = () => {
      this.handleWorkerDied()
    }
  }

  // ---------- 服务启动 ----------

  async initialize(): Promise<void> {
    await this.mediasoupService.initialize()
  }

  // ---------- 连接生命周期 ----------

  registerConnection(
    connectionId: string,
    projectId: string,
    userId: string,
    username: string,
    ws: WsSocket,
  ): void {
    this.participants.set(connectionId, {
      connectionId,
      projectId,
      userId,
      username,
      channelId: null,
      muted: false,
      ws,
      consumers: new Map(),
    })
  }

  async unregisterConnection(connectionId: string): Promise<void> {
    const participant = this.participants.get(connectionId)
    if (!participant) return
    if (participant.channelId) {
      await this.leaveChannelInternal(participant)
    }
    this.participants.delete(connectionId)
  }

  // ---------- 频道 ----------

  listChannelDtos(projectId: string): VoiceChannelDto[] {
    const records = listVoiceChannels(projectId)
    return records.map((record) => this.toChannelDto(record))
  }

  createChannel(
    projectId: string,
    name: string,
    userId: string,
    maxParticipants = VOICE_DEFAULT_MAX_PARTICIPANTS,
  ): VoiceChannelDto {
    const record = createVoiceChannel(projectId, name, userId, maxParticipants)
    this.broadcastSnapshot(projectId)
    return this.toChannelDto(record)
  }

  async deleteChannel(projectId: string, channelId: string): Promise<void> {
    const record = deleteVoiceChannel(projectId, channelId)
    if (!record) throw new ApiError(404, 'CHANNEL_NOT_FOUND', '频道不存在')
    const projectChannels = this.channels.get(projectId)
    const state = projectChannels?.get(channelId)
    if (state) {
      for (const participant of [...state.participants.values()]) {
        await this.leaveChannelInternal(participant)
      }
      projectChannels?.delete(channelId)
      if (projectChannels?.size === 0) this.channels.delete(projectId)
    }
    this.broadcastSnapshot(projectId)
  }

  // ---------- 加入/离开 ----------

  private enqueueOperation<T>(fn: () => Promise<T>): Promise<T> {
    const result = this.operationQueue.then(fn, fn)
    this.operationQueue = result.then(
      () => undefined,
      () => undefined,
    )
    return result
  }

  async joinChannel(connectionId: string, channelId: string): Promise<void> {
    return this.enqueueOperation(() => this.joinChannelInternal(connectionId, channelId))
  }

  private async joinChannelInternal(connectionId: string, channelId: string): Promise<void> {
    const participant = this.participants.get(connectionId)
    if (!participant) throw new ApiError(400, 'VALIDATION', '未建立语音连接')
    if (participant.channelId) {
      throw new ApiError(409, 'ALREADY_IN_CHANNEL', '已在频道中，请先离开当前频道')
    }

    const record = findVoiceChannelById(participant.projectId, channelId)
    if (!record) throw new ApiError(404, 'CHANNEL_NOT_FOUND', '频道不存在')

    let projectChannels = this.channels.get(participant.projectId)
    if (!projectChannels) {
      projectChannels = new Map()
      this.channels.set(participant.projectId, projectChannels)
    }
    let state = projectChannels.get(channelId)
    if (!state) {
      state = { record, participants: new Map() }
      projectChannels.set(channelId, state)
    }

    if (state.participants.size >= record.max_participants) {
      throw new ApiError(409, 'CHANNEL_FULL', '频道已满（上限 8 人）')
    }

    state.participants.set(connectionId, participant)
    participant.channelId = channelId

    const sendTransport = await this.mediasoupService.createTransport(participant.projectId)
    const recvTransport = await this.mediasoupService.createTransport(participant.projectId)
    participant.sendTransport = sendTransport.transport
    participant.recvTransport = recvTransport.transport
    sendTransport.transport.on('routerclose', () => {
      void this.handleTransportRouterClosed(participant, sendTransport.params.id)
    })
    recvTransport.transport.on('routerclose', () => {
      void this.handleTransportRouterClosed(participant, recvTransport.params.id)
    })

    const routerRtpCapabilities = this.mediasoupService.routerRtpCapabilities(participant.projectId)

    const currentParticipants = [...state.participants.values()].map(toParticipantDto)
    this.send(participant, {
      type: 'joined',
      channel_id: channelId,
      participants: currentParticipants,
      router_rtp_capabilities: routerRtpCapabilities,
    })
    this.send(participant, {
      type: 'transport.created',
      transport_id: sendTransport.params.id,
      direction: 'send',
      params: sendTransport.params,
    })
    this.send(participant, {
      type: 'transport.created',
      transport_id: recvTransport.params.id,
      direction: 'recv',
      params: recvTransport.params,
    })

    for (const other of state.participants.values()) {
      if (other.connectionId === connectionId) continue
      this.send(other, { type: 'peer.joined', participant: toParticipantDto(participant) })
    }
    this.broadcastSnapshot(participant.projectId)
  }

  async leaveChannel(connectionId: string): Promise<void> {
    const participant = this.participants.get(connectionId)
    if (!participant) throw new ApiError(400, 'VALIDATION', '未建立语音连接')
    if (!participant.channelId) return
    await this.leaveChannelInternal(participant)
    if (participant.projectId) this.broadcastSnapshot(participant.projectId)
  }

  // ---------- mediasoup 信令 ----------

  async setRtpCapabilities(connectionId: string, rtpCapabilities: RtpCapabilities): Promise<void> {
    const participant = this.participants.get(connectionId)
    if (!participant) throw new ApiError(400, 'VALIDATION', '未建立语音连接')
    participant.rtpCapabilities = rtpCapabilities
  }

  async handleTransportConnect(
    _connectionId: string,
    transportId: string,
    dtlsParameters: DtlsParameters,
  ): Promise<void> {
    await this.mediasoupService.connectTransport(transportId, dtlsParameters)
  }

  async handleProduce(
    connectionId: string,
    transportId: string,
    kind: MediaKind,
    rtpParameters: RtpParameters,
  ): Promise<string> {
    const participant = this.participants.get(connectionId)
    if (!participant?.channelId) {
      throw new ApiError(400, 'VALIDATION', '尚未加入频道')
    }
    if (participant.producer) {
      throw new ApiError(409, 'ALREADY_PRODUCING', '已经发布音频')
    }

    const producer = await this.mediasoupService.produceTracked(transportId, kind, rtpParameters)
    participant.producer = producer
    this.producerOwners.set(producer.id, connectionId)
    this.producerUserIds.set(producer.id, participant.userId)
    producer.on('transportclose', () => {
      void this.handleProducerUnexpectedClose(connectionId, producer.id)
    })

    const state = this.channels.get(participant.projectId)?.get(participant.channelId)
    if (!state) return producer.id

    // 新成员的声音 → 已存在成员
    for (const other of state.participants.values()) {
      if (other.connectionId === connectionId) continue
      await this.ensureConsumer(producer, other)
    }

    // 已存在成员的声音 → 新成员
    for (const other of state.participants.values()) {
      if (other.connectionId === connectionId) continue
      if (other.producer) {
        await this.ensureConsumer(other.producer, participant)
      }
    }

    return producer.id
  }

  async handleConsumerResume(_connectionId: string, consumerId: string): Promise<void> {
    await this.mediasoupService.resumeConsumer(consumerId)
  }

  async setMuted(connectionId: string, muted: boolean): Promise<void> {
    const participant = this.participants.get(connectionId)
    if (!participant) return
    participant.muted = muted
    if (participant.producer) {
      if (muted) {
        await this.mediasoupService.pauseProducer(participant.producer.id)
      } else {
        await this.mediasoupService.resumeProducer(participant.producer.id)
      }
      this.notifyProducerStateToConsumers(participant, muted ? 'consumer.paused' : 'consumer.resumed')
    }
    if (participant.channelId && participant.projectId) {
      this.broadcastParticipants(participant.projectId, participant.channelId)
    }
  }

  async setSpeaking(connectionId: string, speaking: boolean): Promise<void> {
    const participant = this.participants.get(connectionId)
    if (!participant?.channelId) return
    const state = this.channels.get(participant.projectId)?.get(participant.channelId)
    if (!state) return
    for (const other of state.participants.values()) {
      this.send(other, {
        type: 'speaker',
        user_id: participant.userId,
        speaking,
      })
    }
  }

  // ---------- 内部 ----------

  private async ensureConsumer(producer: Producer, target: VoiceParticipant): Promise<void> {
    if (!target.recvTransport || !target.rtpCapabilities) return
    if (target.consumers.has(producer.id)) return
    if (!this.mediasoupService.canConsume(target.recvTransport.id, producer.id, target.rtpCapabilities)) {
      return
    }

    let consumer: Consumer
    try {
      consumer = await this.mediasoupService.consume(
        target.recvTransport.id,
        producer.id,
        target.rtpCapabilities,
      )
    } catch (error) {
      console.error('[ellia-server] voice consumer create failed:', error)
      return
    }
    target.consumers.set(producer.id, consumer)
    this.consumerOwners.set(consumer.id, target.connectionId)
    consumer.on('transportclose', () => {
      void this.handleConsumerUnexpectedClose(target.connectionId, consumer.id, producer.id)
    })
    consumer.on('producerclose', () => {
      void this.handleConsumerUnexpectedClose(target.connectionId, consumer.id, producer.id)
    })

    const producerUserId = this.producerUserIds.get(producer.id)
    this.send(target, {
      type: 'consumer.created',
      consumer_id: consumer.id,
      producer_id: producer.id,
      producer_user_id: producerUserId,
      kind: consumer.kind,
      rtp_parameters: consumer.rtpParameters,
      paused: true,
    })
  }

  private notifyProducerStateToConsumers(
    participant: VoiceParticipant,
    messageType: 'consumer.paused' | 'consumer.resumed',
  ): void {
    if (!participant.producer) return
    const state = participant.channelId
      ? this.channels.get(participant.projectId)?.get(participant.channelId)
      : undefined
    for (const other of state?.participants.values() ?? []) {
      if (other.connectionId === participant.connectionId) continue
      const consumer = other.consumers.get(participant.producer.id)
      if (!consumer) continue
      this.send(other, {
        type: messageType,
        consumer_id: consumer.id,
        producer_id: participant.producer.id,
      })
    }
  }

  private async handleTransportRouterClosed(
    participant: VoiceParticipant,
    transportId: string,
  ): Promise<void> {
    this.send(participant, { type: 'transport.closed', transport_id: transportId })
    if (participant.sendTransport?.id === transportId) participant.sendTransport = undefined
    if (participant.recvTransport?.id === transportId) participant.recvTransport = undefined
  }

  private async handleProducerUnexpectedClose(
    connectionId: string,
    producerId: string,
  ): Promise<void> {
    const participant = this.participants.get(connectionId)
    if (!participant || participant.producer?.id !== producerId) return
    await this.removeConsumersForProducer(producerId)
    this.send(participant, { type: 'producer.closed', producer_id: producerId })
    participant.producer = undefined
  }

  private handleConsumerUnexpectedClose(
    connectionId: string,
    consumerId: string,
    producerId: string,
  ): void {
    const target = this.participants.get(connectionId)
    if (!target) return
    const consumer = target.consumers.get(producerId)
    if (!consumer || consumer.id !== consumerId) return
    target.consumers.delete(producerId)
    this.consumerOwners.delete(consumerId)
    this.send(target, {
      type: 'consumer.closed',
      consumer_id: consumerId,
      producer_id: producerId,
    })
  }

  private handleWorkerDied(): void {
    console.error('[ellia-server] mediasoup worker died, releasing all voice sessions')
    this.channels.clear()
    this.producerOwners.clear()
    this.producerUserIds.clear()
    this.consumerOwners.clear()
    for (const participant of this.participants.values()) {
      participant.channelId = null
      participant.muted = false
      participant.sendTransport = undefined
      participant.recvTransport = undefined
      participant.producer = undefined
      participant.consumers.clear()
      participant.rtpCapabilities = undefined
      this.send(participant, {
        type: 'voice.error',
        code: 'WORKER_RESTART',
        message: '语音服务重启，请重新加入频道',
      })
      this.send(participant, { type: 'left', channel_id: '' })
    }
  }

  private async removeConsumersForProducer(
    producerId: string,
    exceptConnectionId?: string,
  ): Promise<void> {
    const ownerConnectionId = this.producerOwners.get(producerId)
    const state = ownerConnectionId
      ? (() => {
          const owner = this.participants.get(ownerConnectionId)
          return owner?.channelId
            ? this.channels.get(owner.projectId)?.get(owner.channelId)
            : undefined
        })()
      : undefined
    for (const other of state?.participants.values() ?? []) {
      if (other.connectionId === exceptConnectionId) continue
      const consumer = other.consumers.get(producerId)
      if (!consumer) continue
      await this.mediasoupService.closeConsumer(consumer.id)
      other.consumers.delete(producerId)
      this.consumerOwners.delete(consumer.id)
      this.send(other, {
        type: 'consumer.closed',
        consumer_id: consumer.id,
        producer_id: producerId,
      })
    }
    this.producerOwners.delete(producerId)
    this.producerUserIds.delete(producerId)
  }

  private async leaveChannelInternal(participant: VoiceParticipant): Promise<void> {
    const channelId = participant.channelId
    const projectId = participant.projectId
    if (!channelId || !projectId) return

    const state = this.channels.get(projectId)?.get(channelId)
    const leavingUserId = participant.userId

    // 关闭本连接作为消费者时收到的 consumer
    for (const consumer of participant.consumers.values()) {
      await this.mediasoupService.closeConsumer(consumer.id)
      this.consumerOwners.delete(consumer.id)
    }
    participant.consumers.clear()

    // 关闭本连接的 producer，并通知其他成员移除对应 consumer
    if (participant.producer) {
      await this.removeConsumersForProducer(participant.producer.id, participant.connectionId)
      participant.producer.close()
      participant.producer = undefined
    }

    // 关闭本连接的 transport
    if (participant.sendTransport) {
      await this.mediasoupService.closeTransport(participant.sendTransport.id)
    }
    if (participant.recvTransport) {
      await this.mediasoupService.closeTransport(participant.recvTransport.id)
    }
    participant.sendTransport = undefined
    participant.recvTransport = undefined

    for (const other of state?.participants.values() ?? []) {
      if (other.connectionId === participant.connectionId) continue
      this.send(other, { type: 'peer.left', participant: toParticipantDto(participant) })
    }

    state?.participants.delete(participant.connectionId)
    if (state && state.participants.size === 0) {
      this.channels.get(projectId)?.delete(channelId)
      if (this.channels.get(projectId)?.size === 0) {
        this.channels.delete(projectId)
      }
    }

    participant.channelId = null
    participant.muted = false
    participant.rtpCapabilities = undefined

    this.send(participant, { type: 'left', channel_id: channelId })
  }

  private toChannelDto(record: VoiceChannelRecord): VoiceChannelDto {
    const state = this.channels.get(record.project_id)?.get(record.id)
    return {
      id: record.id,
      name: record.name,
      max_participants: record.max_participants,
      participant_count: state?.participants.size ?? 0,
    }
  }

  private broadcastParticipants(projectId: string, channelId: string): void {
    const state = this.channels.get(projectId)?.get(channelId)
    if (!state) return
    const participants = [...state.participants.values()].map(toParticipantDto)
    for (const participant of state.participants.values()) {
      this.send(participant, {
        type: 'participants.snapshot',
        channel_id: channelId,
        participants,
      })
    }
    this.broadcastSnapshot(projectId)
  }

  private broadcastSnapshot(projectId: string): void {
    const channels = this.listChannelDtos(projectId)
    for (const participant of this.participants.values()) {
      if (participant.projectId === projectId) {
        this.send(participant, { type: 'channels.snapshot', channels })
      }
    }
  }

  private send(participant: VoiceParticipant, message: VoiceServerMessage): void {
    if (participant.ws.readyState === WebSocket.OPEN) {
      participant.ws.send(JSON.stringify(message))
    }
  }
}

function toParticipantDto(participant: VoiceParticipant): VoiceParticipantDto {
  return {
    id: participant.userId,
    username: participant.username,
    muted: participant.muted,
  }
}

let instance: VoiceManager | undefined

export function getVoiceManager(config: ServerConfig): VoiceManager {
  instance ??= new VoiceManager(config)
  return instance
}

export function createConnectionId(): string {
  return randomUUID()
}
