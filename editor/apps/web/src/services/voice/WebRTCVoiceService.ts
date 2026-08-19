import { Device } from 'mediasoup-client'
import type * as mediasoupClient from 'mediasoup-client'

type Consumer = mediasoupClient.types.Consumer
type Producer = mediasoupClient.types.Producer
type Transport = mediasoupClient.types.Transport
type RtpCapabilities = mediasoupClient.types.RtpCapabilities

import type { VoiceChannelDto, VoiceParticipantDto } from '@ellia/puzzle-schema'

import {
  createVoiceChannel,
  deleteVoiceChannel,
  listVoiceChannels,
} from '../../client/rest/voice'
import {
  type VoiceConnectionStatus,
  type VoiceService,
  type VoiceServiceEvent,
  type VoiceServiceEvents,
} from './VoiceService'

interface ServerMessage {
  type: string
  ref?: string
  [key: string]: unknown
}

type PendingRequest = {
  resolve: (message: ServerMessage) => void
  reject: (error: Error) => void
}

type Handler = (...args: any[]) => void

const AUDIO_BITRATE = 128_000

let refCounter = 0

export class WebRTCVoiceService implements VoiceService {
  private socket: WebSocket | null = null
  private projectId: string | null = null
  private statusValue: VoiceConnectionStatus = 'idle'
  private handlers = new Map<VoiceServiceEvent, Set<Handler>>()

  private device: Device | null = null
  private sendTransport: Transport | null = null
  private recvTransport: Transport | null = null
  private localStream: MediaStream | null = null
  private producer: Producer | null = null
  private routerRtpCapabilities: RtpCapabilities | null = null
  private currentChannelId: string | null = null
  private consumers = new Map<string, Consumer>() // producerId -> consumer
  private pendingRequests = new Map<string, PendingRequest>()
  private transportsReady = false
  private audioContext: AudioContext | null = null
  private noiseSuppressionValue = false
  private micVolumeValue = 1
  private silenceThresholdValue = 0.1
  private micSourceNode: MediaStreamAudioSourceNode | null = null
  private micGainNode: GainNode | null = null
  private micDestination: MediaStreamAudioDestinationNode | null = null
  private micAnalyser: AnalyserNode | null = null
  private vadTimer: number | null = null
  private speakingValue = false
  private manualMuted = false

  get status(): VoiceConnectionStatus {
    return this.statusValue
  }

  async connect(projectId: string): Promise<void> {
    if (this.socket && this.socket.readyState <= WebSocket.OPEN && this.projectId === projectId) {
      return
    }
    this.projectId = projectId
    this.setStatus('connecting')

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${protocol}://${window.location.host}/ws/projects/${encodeURIComponent(projectId)}/voice`

    await new Promise<void>((resolve, reject) => {
      const socket = new WebSocket(url)
      this.socket = socket
      socket.onopen = () => {
        this.setStatus('connected')
        resolve()
      }
      socket.onerror = () => {
        if (this.socket === socket) {
          this.setStatus('error', '语音信令连接失败')
        }
        socket.close()
      }
      socket.onmessage = (event) => this.handleMessage(event)
      socket.onclose = () => {
        if (this.socket === socket) {
          this.socket = null
          this.setStatus('idle')
        }
      }
      setTimeout(() => {
        if (this.socket === socket && socket.readyState !== WebSocket.OPEN) {
          reject(new Error('语音信令连接超时'))
        }
      }, 5000)
    })
  }

  disconnect(): void {
    this.cleanupMedia()
    this.currentChannelId = null
    this.projectId = null
    this.pendingRequests.clear()
    this.socket?.close()
    this.socket = null
    this.setStatus('idle')
  }

  async listChannels(): Promise<VoiceChannelDto[]> {
    if (!this.projectId) return []
    const { channels } = await listVoiceChannels(this.projectId)
    return channels
  }

  async createChannel(name: string, maxParticipants?: number): Promise<VoiceChannelDto> {
    if (!this.projectId) throw new Error('尚未连接语音服务')
    const { channel } = await createVoiceChannel(this.projectId, name, maxParticipants)
    await this.refreshChannels()
    return channel
  }

  async deleteChannel(channelId: string): Promise<void> {
    if (!this.projectId) throw new Error('尚未连接语音服务')
    await deleteVoiceChannel(this.projectId, channelId)
    await this.refreshChannels()
  }

  async joinChannel(channelId: string): Promise<void> {
    await this.ensureSocket()
    this.ensureAudioContext()
    await this.ensureMicrophone()
    this.currentChannelId = channelId
    await this.request({ type: 'channels.join', channel_id: channelId })
  }

  async leaveChannel(): Promise<void> {
    if (this.currentChannelId) {
      await this.request({ type: 'channels.leave' }).catch(() => undefined)
    }
    this.cleanupMedia()
    this.currentChannelId = null
  }

  setMuted(muted: boolean): void {
    this.manualMuted = muted
    if (this.producer) {
      if (muted) {
        this.producer.pause()
      } else if (this.speakingValue) {
        this.producer.resume()
      }
    }
    if (this.localStream) {
      for (const track of this.localStream.getAudioTracks()) {
        track.enabled = !muted
      }
    }
    this.send({ type: 'mic.state', muted })
  }

  async setNoiseSuppression(enabled: boolean): Promise<void> {
    this.noiseSuppressionValue = enabled
    if (!this.localStream || !this.producer) return
    // 重新采集麦克风并替换发送轨道
    this.teardownMicGraph()
    this.localStream.getTracks().forEach((track) => track.stop())
    this.localStream = null
    await this.ensureMicrophone()
    if (this.producer && this.micDestination) {
      const track = this.micDestination.stream.getAudioTracks()[0]
      if (track) await this.producer.replaceTrack({ track })
    }
  }

  setMicVolume(volume: number): void {
    this.micVolumeValue = volume
    if (this.micGainNode && this.audioContext) {
      this.micGainNode.gain.setTargetAtTime(volume, this.audioContext.currentTime, 0.05)
    }
  }

  setSilenceThreshold(threshold: number): void {
    this.silenceThresholdValue = threshold
  }

  on<K extends VoiceServiceEvent>(event: K, handler: VoiceServiceEvents[K]): () => void {
    const listeners = this.handlers.get(event) ?? new Set<Handler>()
    listeners.add(handler as Handler)
    this.handlers.set(event, listeners)
    return () => {
      listeners.delete(handler as Handler)
    }
  }

  private async ensureSocket(): Promise<void> {
    if (!this.projectId) throw new Error('尚未连接语音服务')
    if (!this.socket || this.socket.readyState === WebSocket.CLOSED) {
      await this.connect(this.projectId)
      return
    }
    if (this.socket.readyState === WebSocket.CONNECTING) {
      await new Promise<void>((resolve, reject) => {
        const socket = this.socket
        socket!.addEventListener('open', () => resolve(), { once: true })
        socket!.addEventListener('error', () => reject(new Error('语音信令连接失败')), { once: true })
      })
    }
  }

  private async ensureMicrophone(): Promise<MediaStream> {
    if (this.localStream) return this.localStream
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: this.noiseSuppressionValue,
        autoGainControl: false,
      },
    })
    this.localStream = stream
    this.buildMicGraph()
    return stream
  }

  private buildMicGraph(): void {
    if (!this.audioContext || !this.localStream) return
    const context = this.audioContext
    const source = context.createMediaStreamSource(this.localStream)
    const gain = context.createGain()
    gain.gain.value = this.micVolumeValue
    const destination = context.createMediaStreamDestination()
    const analyser = context.createAnalyser()
    analyser.fftSize = 512
    analyser.smoothingTimeConstant = 0.2

    source.connect(gain)
    gain.connect(destination)
    gain.connect(analyser)

    this.micSourceNode = source
    this.micGainNode = gain
    this.micDestination = destination
    this.micAnalyser = analyser
  }

  private teardownMicGraph(): void {
    this.micSourceNode?.disconnect()
    this.micGainNode?.disconnect()
    this.micDestination?.disconnect()
    this.micAnalyser?.disconnect()
    this.micSourceNode = null
    this.micGainNode = null
    this.micDestination = null
    this.micAnalyser = null
  }

  private getMicTrack(): MediaStreamTrack | undefined {
    if (this.micDestination) {
      return this.micDestination.stream.getAudioTracks()[0]
    }
    return this.localStream?.getAudioTracks()[0]
  }

  private startVad(): void {
    this.stopVad()
    if (!this.micAnalyser) return
    this.vadTimer = window.setInterval(() => {
      const analyser = this.micAnalyser
      if (!analyser) return
      const data = new Float32Array(analyser.fftSize)
      analyser.getFloatTimeDomainData(data)
      let sum = 0
      for (let i = 0; i < data.length; i += 1) {
        sum += data[i]! * data[i]!
      }
      const rms = Math.sqrt(sum / data.length)
      const rawSpeaking = rms > this.silenceThresholdValue
      const speaking = rawSpeaking && !this.manualMuted
      if (speaking !== this.speakingValue) {
        this.speakingValue = speaking
        this.send({ type: 'speaking', speaking })
        if (!this.manualMuted && this.producer) {
          if (speaking) {
            this.producer.resume()
          } else {
            this.producer.pause()
          }
        }
      }
    }, 200)
  }

  private stopVad(): void {
    if (this.vadTimer !== null) {
      clearInterval(this.vadTimer)
      this.vadTimer = null
    }
    this.speakingValue = false
  }

  private ensureAudioContext(): void {
    if (this.audioContext) return
    const AudioContextCtor =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AudioContextCtor) return
    this.audioContext = new AudioContextCtor()
    if (this.audioContext.state === 'suspended') {
      void this.audioContext.resume()
    }
  }

  // ---------- 消息处理 ----------

  private handleMessage(event: MessageEvent<string>): void {
    let message: ServerMessage
    try {
      message = JSON.parse(event.data) as ServerMessage
    } catch {
      return
    }

    if (message.ref && this.pendingRequests.has(message.ref)) {
      const pending = this.pendingRequests.get(message.ref)!
      this.pendingRequests.delete(message.ref)
      if (message.type === 'error') {
        pending.reject(new Error(String(message.message ?? '语音错误')))
      } else {
        pending.resolve(message)
      }
      return
    }

    switch (message.type) {
      case 'error':
        this.setStatus('error', String(message.message ?? '语音错误'))
        return
      case 'voice.error':
        if (message.code === 'WORKER_RESTART') {
          const closedChannelId = this.currentChannelId ?? ''
          this.cleanupMedia()
          this.currentChannelId = null
          this.setStatus('error', String(message.message ?? '语音服务重启'))
          this.emit('left', closedChannelId)
          return
        }
        this.setStatus('error', String(message.message ?? '语音错误'))
        return
      case 'transport.closed':
        this.handleTransportClosed(String(message.transport_id ?? ''))
        return
      case 'producer.closed':
        if (this.producer && String(message.producer_id ?? '') === this.producer.id) {
          this.producer.close()
          this.producer = null
        }
        return
      case 'consumer.paused':
        this.pauseConsumerByProducer(String(message.producer_id ?? ''))
        return
      case 'consumer.resumed':
        this.resumeConsumerByProducer(String(message.producer_id ?? ''))
        return
      case 'channels.snapshot':
        this.emit('channels', (message.channels as VoiceChannelDto[]) ?? [])
        return
      case 'joined':
        this.routerRtpCapabilities = message.router_rtp_capabilities as RtpCapabilities | null
        this.currentChannelId = String(message.channel_id ?? '')
        this.emit('joined', this.currentChannelId, (message.participants as VoiceParticipantDto[]) ?? [])
        return
      case 'transport.created':
        void this.handleTransportCreated(message).catch((error) => {
          console.error('[voice] transport setup failed:', error)
        })
        return
      case 'producer.created':
        return
      case 'consumer.created':
        void this.handleConsumerCreated(message).catch((error) => {
          console.error('[voice] consumer create failed:', error)
        })
        return
      case 'consumer.closed':
        this.handleConsumerClosed(message)
        return
      case 'speaker':
        this.emit('speaker', String(message.user_id ?? ''), message.speaking === true)
        return
      case 'left':
        this.cleanupMedia()
        this.emit('left', String(message.channel_id ?? ''))
        return
      case 'peer.joined':
        this.emit('peer.joined', message.participant as VoiceParticipantDto)
        return
      case 'peer.left':
        this.emit('peer.left', message.participant as VoiceParticipantDto)
        return
      case 'participants.snapshot':
        this.emit(
          'participants',
          String(message.channel_id ?? ''),
          (message.participants as VoiceParticipantDto[]) ?? [],
        )
        return
      default:
        return
    }
  }

  private request<T = ServerMessage>(payload: Record<string, unknown>): Promise<T> {
    const ref = `voice-${++refCounter}`
    return new Promise<T>((resolve, reject) => {
      this.pendingRequests.set(ref, {
        resolve: (message) => resolve(message as unknown as T),
        reject,
      })
      this.send({ ...payload, ref })
    })
  }

  // ---------- mediasoup 客户端流程 ----------

  private async handleTransportCreated(message: ServerMessage): Promise<void> {
    const params = message.params as {
      id: string
      iceParameters: unknown
      iceCandidates: unknown
      dtlsParameters: unknown
    }
    const direction = message.direction as 'send' | 'recv'
    if (!this.device) {
      if (!this.routerRtpCapabilities) return
      const device = new Device()
      await device.load({ routerRtpCapabilities: this.routerRtpCapabilities })
      this.device = device
    }

    if (direction === 'send' && !this.sendTransport) {
      this.sendTransport = this.device.createSendTransport({
        id: params.id,
        iceParameters: params.iceParameters as never,
        iceCandidates: params.iceCandidates as never,
        dtlsParameters: params.dtlsParameters as never,
      })
      this.setupTransport(this.sendTransport, true)
    } else if (direction === 'recv' && !this.recvTransport) {
      this.recvTransport = this.device.createRecvTransport({
        id: params.id,
        iceParameters: params.iceParameters as never,
        iceCandidates: params.iceCandidates as never,
        dtlsParameters: params.dtlsParameters as never,
      })
      this.setupTransport(this.recvTransport, false)
    }

    if (!this.transportsReady && this.sendTransport && this.recvTransport && this.device) {
      this.transportsReady = true
      // 先告知服务端本端 RTP 能力，再发布音频
      await this.request({ type: 'rtp.capabilities', rtp_capabilities: this.device.recvRtpCapabilities })
      await this.produceLocalAudio()
    }
  }

  private setupTransport(transport: Transport, isSend: boolean): void {
    transport.on('connect', ({ dtlsParameters }, callback, errback) => {
      this.request({
        type: 'transport.connect',
        transport_id: transport.id,
        dtls_parameters: dtlsParameters,
      })
        .then(() => callback())
        .catch((error: Error) => errback(error))
    })

    if (isSend) {
      transport.on('produce', async ({ kind, rtpParameters }, callback, errback) => {
        try {
          const response = await this.request<{ producer_id: string }>({
            type: 'produce',
            transport_id: transport.id,
            kind,
            rtp_parameters: rtpParameters,
          })
          callback({ id: response.producer_id })
        } catch (error) {
          errback(error as Error)
        }
      })
    }
  }

  private async produceLocalAudio(): Promise<void> {
    if (!this.sendTransport || !this.localStream || this.producer) return
    const track = this.getMicTrack()
    if (!track) return
    const producer = await this.sendTransport.produce({
      track,
      encodings: [{ maxBitrate: AUDIO_BITRATE }],
      appData: { source: 'mic' },
    })
    this.producer = producer
    this.startVad()
  }

  private async handleConsumerCreated(message: ServerMessage): Promise<void> {
    if (!this.recvTransport) return
    const consumerId = String(message.consumer_id ?? '')
    const producerId = String(message.producer_id ?? '')
    const producerUserId = String(message.producer_user_id ?? '')
    const kind = String(message.kind ?? 'audio') as 'audio' | 'video'
    const rtpParameters = message.rtp_parameters as never

    const consumer = await this.recvTransport.consume({
      id: consumerId,
      producerId,
      kind,
      rtpParameters,
      appData: { producerUserId },
    })
    this.consumers.set(producerId, consumer)

    // 先恢复本地 consumer，让 track 处于可播放状态，再暴露给 UI
    consumer.resume()
    let receivedTrack: MediaStreamTrack | null = null
    try {
      receivedTrack = consumer.track
    } catch {
      receivedTrack = null
    }
    if (receivedTrack) {
      console.log(
        `[voice] remote-track emitted userId=${producerUserId} enabled=${receivedTrack.enabled}`,
      )
      this.emit('remote-track', producerUserId, new MediaStream([receivedTrack]))
    } else {
      console.warn('[voice] remote consumer created but track is null', consumerId)
    }
    consumer.on('trackended', () => {
      this.emit('remote-track-ended', producerUserId)
    })

    await this.request({ type: 'consumer.resume', consumer_id: consumerId }).catch(() => undefined)
  }

  private handleConsumerClosed(message: ServerMessage): void {
    const producerId = String(message.producer_id ?? '')
    const consumer = this.consumers.get(producerId)
    if (!consumer) return
    const userId = String(consumer.appData?.producerUserId ?? '')
    consumer.close()
    this.consumers.delete(producerId)
    if (userId) this.emit('remote-track-ended', userId)
  }

  private handleTransportClosed(transportId: string): void {
    if (this.sendTransport?.id === transportId) {
      this.sendTransport.close()
      this.sendTransport = null
    }
    if (this.recvTransport?.id === transportId) {
      this.recvTransport.close()
      this.recvTransport = null
    }
  }

  private pauseConsumerByProducer(producerId: string): void {
    const consumer = this.consumers.get(producerId)
    if (consumer) consumer.pause()
  }

  private resumeConsumerByProducer(producerId: string): void {
    const consumer = this.consumers.get(producerId)
    if (consumer) consumer.resume()
  }

  private cleanupMedia(): void {
    this.stopVad()
    this.manualMuted = false
    this.producer?.close()
    this.producer = null
    for (const consumer of this.consumers.values()) consumer.close()
    this.consumers.clear()
    this.sendTransport?.close()
    this.sendTransport = null
    this.recvTransport?.close()
    this.recvTransport = null
    this.teardownMicGraph()
    this.localStream?.getTracks().forEach((track) => track.stop())
    this.localStream = null
    this.device = null
    this.routerRtpCapabilities = null
    this.transportsReady = false
    void this.audioContext?.close()
    this.audioContext = null
  }

  // ---------- 基础工具 ----------

  private refreshChannels(): Promise<void> {
    return this.listChannels().then((channels) => {
      this.emit('channels', channels)
    })
  }

  private send(payload: Record<string, unknown>): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload))
    }
  }

  private setStatus(status: VoiceConnectionStatus, error?: string): void {
    if (this.statusValue === status && !error) return
    this.statusValue = status
    this.emit('status', status, error)
  }

  private emit<K extends VoiceServiceEvent>(event: K, ...args: Parameters<VoiceServiceEvents[K]>): void {
    const listeners = this.handlers.get(event)
    if (!listeners) return
    for (const listener of listeners) {
      listener(...args)
    }
  }
}
