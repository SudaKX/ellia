import { computed, inject, ref, type ComputedRef, type InjectionKey, type Ref } from 'vue'

export type AudioBus = 'ui' | 'system'
export type AudioCue = 'window-open' | 'window-focus' | 'window-minimize' | 'window-close' | 'system-alert'

const ANALYSER_FFT_SIZE = 512

type AudioContextStatus = 'idle' | 'unavailable' | AudioContextState

interface CueDefinition {
  bus: AudioBus
  type: OscillatorType
  startFrequency: number
  endFrequency: number
  duration: number
  gain: number
}

const CUES: Record<AudioCue, CueDefinition> = {
  'window-open': {
    bus: 'ui',
    type: 'sine',
    startFrequency: 392,
    endFrequency: 587.33,
    duration: 0.14,
    gain: 0.1,
  },
  'window-focus': {
    bus: 'ui',
    type: 'triangle',
    startFrequency: 554.37,
    endFrequency: 659.25,
    duration: 0.08,
    gain: 0.065,
  },
  'window-minimize': {
    bus: 'ui',
    type: 'sine',
    startFrequency: 523.25,
    endFrequency: 293.66,
    duration: 0.13,
    gain: 0.085,
  },
  'window-close': {
    bus: 'ui',
    type: 'triangle',
    startFrequency: 392,
    endFrequency: 220,
    duration: 0.11,
    gain: 0.075,
  },
  'system-alert': {
    bus: 'system',
    type: 'square',
    startFrequency: 246.94,
    endFrequency: 196,
    duration: 0.2,
    gain: 0.045,
  },
}

export interface AudioService {
  isSupported: boolean
  contextStatus: Ref<AudioContextStatus>
  isMuted: Ref<boolean>
  masterVolume: Ref<number>
  busVolumes: Ref<Record<AudioBus, number>>
  isReady: ComputedRef<boolean>
  spectrumSize: number
  unlock: () => Promise<boolean>
  play: (cue: AudioCue) => void
  /** 播放音频文件，通过 Web Audio 图输出（会显示在频谱上），音量受主音量和静音控制 */
  playFile: (url: string, bus?: AudioBus) => void
  /** 停止当前正在播放的文件 */
  stopFile: () => void
  readSpectrumData: (samples: Uint8Array<ArrayBuffer>) => boolean
  setMuted: (muted: boolean) => void
  setMasterVolume: (volume: number) => void
  setBusVolume: (bus: AudioBus, volume: number) => void
  suspend: () => Promise<void>
  dispose: () => Promise<void>
}

export const AudioServiceKey: InjectionKey<AudioService> = Symbol('AudioService')

function clampVolume(volume: number) {
  return Math.min(1, Math.max(0, volume))
}

export function createAudioService(): AudioService {
  const isSupported = typeof window !== 'undefined' && typeof window.AudioContext !== 'undefined'
  const contextStatus = ref<AudioContextStatus>(isSupported ? 'idle' : 'unavailable')
  const isMuted = ref(false)
  const masterVolume = ref(0.55)
  const busVolumes = ref<Record<AudioBus, number>>({
    ui: 0.8,
    system: 0.7,
  })
  const isReady = computed(() => contextStatus.value === 'running')

  let context: AudioContext | null = null
  let masterGain: GainNode | null = null
  let compressor: DynamicsCompressorNode | null = null
  let analyser: AnalyserNode | null = null
  let unlockPromise: Promise<boolean> | null = null
  const busGains = new Map<AudioBus, GainNode>()
  /** 当前正在播放的文件音频元素，用于打断前一个 */
  let activeFileAudio: HTMLAudioElement | null = null

  function updateGain(gain: GainNode | null, value: number) {
    if (!gain || !context) return

    gain.gain.cancelScheduledValues(context.currentTime)
    gain.gain.setTargetAtTime(value, context.currentTime, 0.015)
  }

  function updateMasterGain() {
    updateGain(masterGain, isMuted.value ? 0 : masterVolume.value)
  }

  function updateBusGain(bus: AudioBus) {
    updateGain(busGains.get(bus) ?? null, busVolumes.value[bus])
  }

  function ensureGraph() {
    if (!isSupported) return null
    if (context) return context

    context = new window.AudioContext()
    contextStatus.value = context.state
    context.addEventListener('statechange', () => {
      contextStatus.value = context?.state ?? 'idle'
    })

    masterGain = context.createGain()
    compressor = context.createDynamicsCompressor()
    compressor.threshold.value = -18
    compressor.knee.value = 12
    compressor.ratio.value = 8
    compressor.attack.value = 0.003
    compressor.release.value = 0.14
    analyser = context.createAnalyser()
    analyser.fftSize = ANALYSER_FFT_SIZE
    analyser.smoothingTimeConstant = 0.78

    for (const bus of ['ui', 'system'] as const) {
      const gain = context.createGain()
      gain.gain.value = busVolumes.value[bus]
      gain.connect(masterGain)
      busGains.set(bus, gain)
    }

    masterGain.gain.value = isMuted.value ? 0 : masterVolume.value
    masterGain.connect(compressor)
    compressor.connect(analyser)
    analyser.connect(context.destination)
    return context
  }

  async function unlock() {
    const audioContext = ensureGraph()
    if (!audioContext) return false
    if (audioContext.state === 'running') return true
    if (unlockPromise) return unlockPromise

    // resume() 可能在部分浏览器/环境下永远不 resolve，
    // 包装一个 2s 超时防止音频系统永久卡死
    unlockPromise = Promise.race([
      audioContext
        .resume()
        .then(() => audioContext.state === 'running')
        .catch(() => false),
      new Promise<boolean>((resolve) => setTimeout(() => resolve(false), 2000)),
    ]).finally(() => {
      unlockPromise = null
    })

    return unlockPromise
  }

  function playNow(cue: AudioCue) {
    if (!context || context.state !== 'running') return

    const definition = CUES[cue]
    const oscillator = context.createOscillator()
    const envelope = context.createGain()
    const startTime = context.currentTime
    const attackEnd = startTime + 0.012
    const endTime = startTime + definition.duration

    oscillator.type = definition.type
    oscillator.frequency.setValueAtTime(definition.startFrequency, startTime)
    oscillator.frequency.exponentialRampToValueAtTime(definition.endFrequency, endTime)
    envelope.gain.setValueAtTime(0.0001, startTime)
    envelope.gain.exponentialRampToValueAtTime(definition.gain, attackEnd)
    envelope.gain.exponentialRampToValueAtTime(0.0001, endTime)

    oscillator.connect(envelope)
    envelope.connect(busGains.get(definition.bus)!)
    oscillator.start(startTime)
    oscillator.stop(endTime + 0.01)
  }

  function play(cue: AudioCue) {
    void unlock().then((ready) => {
      if (ready) playNow(cue)
    })
  }

  function readSpectrumData(samples: Uint8Array<ArrayBuffer>) {
    if (!analyser || !context || context.state !== 'running' || samples.length !== analyser.frequencyBinCount) {
      return false
    }

    analyser.getByteFrequencyData(samples)
    return true
  }

  function setMuted(muted: boolean) {
    isMuted.value = muted
    updateMasterGain()
  }

  function setMasterVolume(volume: number) {
    masterVolume.value = clampVolume(volume)
    updateMasterGain()
  }

  function setBusVolume(bus: AudioBus, volume: number) {
    busVolumes.value = {
      ...busVolumes.value,
      [bus]: clampVolume(volume),
    }
    updateBusGain(bus)
  }

  /**
   * 播放音频文件，通过 Web Audio 图输出。
   * 音频走 busGain → masterGain → compressor → analyser → destination，
   * 因此会显示在频谱上，且受主音量/静音/总线音量控制。
   *
   * @param url - 音频文件 URL
   * @param bus - 总线（'ui' | 'system'），默认 'ui'
   */
  function playFile(url: string, bus: AudioBus = 'ui') {
    // 打断前一个文件播放
    if (activeFileAudio) {
      activeFileAudio.pause()
      activeFileAudio.remove()
      activeFileAudio = null
    }

    const audioEl = new Audio(url)
    activeFileAudio = audioEl

    const done = () => {
      source?.disconnect()
      activeFileAudio = null
      audioEl.remove()
    }

    let source: MediaElementAudioSourceNode | null = null

    void unlock().then((ready) => {
      if (ready && context && !isMuted.value && masterVolume.value > 0) {
        // Web Audio 图可用：走频谱 + 音量控制
        try {
          source = context.createMediaElementSource(audioEl)
          source.connect(busGains.get(bus)!)
        } catch {
          source = null
          // Web Audio 图创建失败，回退到直接播放并手动控制音量
          audioEl.volume = masterVolume.value * (busVolumes.value[bus] ?? 0.8)
        }
      } else {
        // Web Audio 不可用，直接播放并手动应用音量
        audioEl.volume = isMuted.value ? 0 : masterVolume.value * (busVolumes.value[bus] ?? 0.8)
      }
      audioEl.play().catch(() => {})
    })

    audioEl.addEventListener('ended', done, { once: true })
  }

  /** 停止当前正在播放的文件 */
  function stopFile() {
    if (activeFileAudio) {
      activeFileAudio.pause()
      activeFileAudio.remove()
      activeFileAudio = null
    }
  }

  async function suspend() {
    if (context?.state === 'running') {
      await context.suspend()
    }
  }

  async function dispose() {
    unlockPromise = null
    busGains.clear()
    masterGain = null
    compressor = null
    analyser = null

    if (context && context.state !== 'closed') {
      await context.close()
    }

    context = null
    contextStatus.value = isSupported ? 'idle' : 'unavailable'
  }

  return {
    isSupported,
    contextStatus,
    isMuted,
    masterVolume,
    busVolumes,
    isReady,
    spectrumSize: ANALYSER_FFT_SIZE / 2,
    unlock,
    play,
    playFile,
    stopFile,
    readSpectrumData,
    setMuted,
    setMasterVolume,
    setBusVolume,
    suspend,
    dispose,
  }
}

export function useAudioService() {
  const service = inject(AudioServiceKey)
  if (!service) {
    throw new Error('AudioService is not available')
  }
  return service
}
