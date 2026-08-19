import { createWorker } from 'mediasoup'
import type * as mediasoup from 'mediasoup'

import type { ServerConfig } from '../config.js'

type Worker = mediasoup.types.Worker
type WebRtcServerType = mediasoup.types.WebRtcServer
type Router = mediasoup.types.Router
export type WebRtcTransport = mediasoup.types.WebRtcTransport
export type Producer = mediasoup.types.Producer
export type Consumer = mediasoup.types.Consumer
type DtlsParameters = mediasoup.types.DtlsParameters
type RtpCapabilities = mediasoup.types.RtpCapabilities
type MediaKind = mediasoup.types.MediaKind
type RtpParameters = mediasoup.types.RtpParameters

export interface CreatedTransport {
  id: string
  iceParameters: mediasoup.types.IceParameters
  iceCandidates: mediasoup.types.IceCandidate[]
  dtlsParameters: mediasoup.types.DtlsParameters
}

const audioCodec: mediasoup.types.RouterRtpCodecCapability = {
  kind: 'audio',
  mimeType: 'audio/opus',
  clockRate: 48000,
  channels: 2,
}

export class MediasoupService {
  private worker: Worker | undefined
  private webRtcServer: WebRtcServerType | undefined
  private readonly routers = new Map<string, Router>()
  private readonly transports = new Map<string, WebRtcTransport>()
  private readonly transportProjects = new Map<string, string>()
  private readonly consumers = new Map<string, Consumer>()
  private ready: Promise<void> | null = null
  onWorkerDied: (() => void) | null = null

  constructor(private readonly config: ServerConfig) {}

  /** 供服务启动时主动初始化 mediasoup（提前暴露端口/worker 问题） */
  async initialize(): Promise<void> {
    await this.ensureReady()
  }

  private ensureReady(): Promise<void> {
    if (!this.ready) {
      this.ready = (async () => {
        const worker = await createWorker({ logLevel: 'warn' })
        this.worker = worker
        worker.on('died', () => {
          console.error('[ellia-server] mediasoup worker died, resetting voice service')
          this.reset()
        })
        this.webRtcServer = await worker.createWebRtcServer({
          listenInfos: [
            {
              protocol: 'udp',
              ip: this.config.voiceMediaListenIp,
              announcedAddress: this.config.voiceMediaAnnouncedAddress,
              port: this.config.voiceMediaPort,
            },
          ],
        })
        console.log(
          `[ellia-server] mediasoup ready: worker=${worker.pid} webrtc-server-port=${this.config.voiceMediaPort}`,
        )
      })()
    }
    return this.ready
  }

  private reset(): void {
    this.worker = undefined
    this.webRtcServer = undefined
    this.routers.clear()
    this.transports.clear()
    this.transportProjects.clear()
    this.consumers.clear()
    this.producers.clear()
    this.ready = null
    this.onWorkerDied?.()
  }

  private async getRouter(projectId: string): Promise<Router> {
    await this.ensureReady()
    let router = this.routers.get(projectId)
    if (!router) {
      router = await this.worker!.createRouter({ mediaCodecs: [audioCodec] })
      this.routers.set(projectId, router)
    }
    return router
  }

  async createTransport(projectId: string): Promise<{
    transport: WebRtcTransport
    params: CreatedTransport
  }> {
    const router = await this.getRouter(projectId)
    const transport = await router.createWebRtcTransport({
      webRtcServer: this.webRtcServer!,
      enableUdp: true,
      enableTcp: false,
      preferUdp: true,
      appData: { projectId },
    })
    this.transports.set(transport.id, transport)
    this.transportProjects.set(transport.id, projectId)
    return {
      transport,
      params: {
        id: transport.id,
        iceParameters: transport.iceParameters,
        iceCandidates: transport.iceCandidates,
        dtlsParameters: transport.dtlsParameters,
      },
    }
  }

  async connectTransport(transportId: string, dtlsParameters: DtlsParameters): Promise<void> {
    const transport = this.transports.get(transportId)
    if (!transport) throw new Error(`transport not found: ${transportId}`)
    await transport.connect({ dtlsParameters })
    console.log(`[ellia-server] voice transport connected: ${transportId}`)
  }

  async produce(transportId: string, kind: MediaKind, rtpParameters: RtpParameters): Promise<Producer> {
    const transport = this.transports.get(transportId)
    if (!transport) throw new Error(`transport not found: ${transportId}`)
    return transport.produce({ kind, rtpParameters, appData: { kind } })
  }

  canConsume(transportId: string, producerId: string, rtpCapabilities: RtpCapabilities): boolean {
    const projectId = this.transportProjects.get(transportId)
    if (!projectId) return false
    const router = this.routers.get(projectId)
    return router?.canConsume({ producerId, rtpCapabilities }) ?? false
  }

  async consume(
    transportId: string,
    producerId: string,
    rtpCapabilities: RtpCapabilities,
  ): Promise<Consumer> {
    const transport = this.transports.get(transportId)
    if (!transport) throw new Error(`transport not found: ${transportId}`)
    const consumer = await transport.consume({
      producerId,
      rtpCapabilities,
      paused: true,
      appData: { transportId, producerId },
    })
    this.consumers.set(consumer.id, consumer)
    consumer.on('transportclose', () => {
      this.consumers.delete(consumer.id)
    })
    consumer.on('producerclose', () => {
      this.consumers.delete(consumer.id)
    })
    console.log(`[ellia-server] voice consumer created: ${consumer.id} (producer ${consumer.producerId})`)
    return consumer
  }

  async resumeConsumer(consumerId: string): Promise<void> {
    const consumer = this.consumers.get(consumerId)
    if (!consumer) throw new Error(`consumer not found: ${consumerId}`)
    await consumer.resume()
  }

  async pauseProducer(producerId: string): Promise<void> {
    const producer = this.findProducer(producerId)
    if (producer) await producer.pause()
  }

  async resumeProducer(producerId: string): Promise<void> {
    const producer = this.findProducer(producerId)
    if (producer) await producer.resume()
  }

  async closeConsumer(consumerId: string): Promise<void> {
    const consumer = this.consumers.get(consumerId)
    if (!consumer) return
    consumer.close()
    this.consumers.delete(consumerId)
  }

  async closeTransport(transportId: string): Promise<void> {
    const transport = this.transports.get(transportId)
    if (!transport) return
    transport.close()
    this.transports.delete(transportId)
    this.transportProjects.delete(transportId)
  }

  routerRtpCapabilities(projectId: string): RtpCapabilities | undefined {
    return this.routers.get(projectId)?.rtpCapabilities
  }

  private readonly producers = new Map<string, Producer>()

  private findProducer(producerId: string): Producer | undefined {
    return this.producers.get(producerId)
  }

  private trackProducer(producer: Producer): void {
    this.producers.set(producer.id, producer)
    producer.on('transportclose', () => {
      this.producers.delete(producer.id)
    })
  }

  // 让 produce() 也登记 producer，便于按 id 查询/暂停
  async produceTracked(
    transportId: string,
    kind: MediaKind,
    rtpParameters: RtpParameters,
  ): Promise<Producer> {
    const producer = await this.produce(transportId, kind, rtpParameters)
    this.trackProducer(producer)
    console.log(`[ellia-server] voice producer created: ${producer.id} (${kind})`)
    return producer
  }
}
