import { watch, onBeforeUnmount } from 'vue'
import { useAudioStore } from '@/stores/audio'

/**
 * 全局音量控制架构：
 *
 * ```
 * AudioStore (masterVolume: 0..1)
 *     │
 *     ├─ SoundMenu.vue ──→ 滑块 UI → setVolume()
 *     │
 *     ├─ useAudio() ──→ watch → GainNode.gain.value
 *     │                  ├─ playBeep(freq, ms)  — 提示音（sine/square/sawtooth）
 *     │                  └─ playTone(freq, ms)  — 通知音（triangle + 淡出包络）
 *     │
 *     └─ App.vue ──→ watch + MutationObserver → 同步 <audio>/<video>.volume
 * ```
 *
 * 为什么用 Web Audio API 而非 DOM `<audio>`？
 * - 音效需要低延迟触发，不需要 DOM 标签。
 * - 一个 GainNode 控制全局，改动一处即对所有音效生效。
 * - 少数 `<video>` 元素由 App.vue 的 MutationObserver 兜底同步。
 */

/** 模块级单例：整个 SPA 共享一个 AudioContext 和一个主 GainNode。 */
let audioCtx: AudioContext | null = null
let masterGain: GainNode | null = null
/** 引用计数：所有调用 useAudio() 的组件卸载后自动关闭 AudioContext。 */
let refCount = 0

function ensureContext(): { ctx: AudioContext; gain: GainNode } {
  if (!audioCtx) {
    audioCtx = new AudioContext()
    masterGain = audioCtx.createGain()
    masterGain.connect(audioCtx.destination)
  }
  return { ctx: audioCtx, gain: masterGain! }
}

/**
 * 音效播放 composable。
 *
 * @example
 * ```ts
 * const { playBeep, playTone } = useAudio()
 * playBeep(440, 150)        // 440Hz 短促提示音
 * playTone(660, 250)        // 660Hz 柔和通知音
 * playBeep(880, 100, 'square')  // 880Hz 方波
 * ```
 *
 * 音量自动跟随 {@link useAudioStore.masterVolume}，无需手动调节。
 * 组件卸载时自动释放 watcher；所有组件卸载后关闭 AudioContext。
 */
export function useAudio() {
  const audioStore = useAudioStore()
  const { ctx, gain } = ensureContext()
  refCount++

  gain.gain.value = audioStore.masterVolume

  const stopWatch = watch(
    () => audioStore.masterVolume,
    (vol) => {
      gain.gain.value = vol
    },
  )

  /**
   * 播放短促提示音。
   * @param frequency  频率（Hz），如 440、880 等
   * @param durationMs 持续时间（毫秒）
   * @param type       波形类型：'sine' | 'square' | 'sawtooth' | 'triangle'
   */
  function playBeep(frequency: number, durationMs: number, type: OscillatorType = 'sine') {
    if (ctx.state === 'suspended') {
      ctx.resume()
    }
    const osc = ctx.createOscillator()
    const envelope = ctx.createGain()
    osc.type = type
    osc.frequency.value = frequency
    envelope.gain.value = 0.15
    const now = ctx.currentTime
    envelope.gain.setValueAtTime(0.15, now)
    envelope.gain.exponentialRampToValueAtTime(0.001, now + durationMs / 1000)
    osc.connect(envelope)
    envelope.connect(gain)
    osc.start(now)
    osc.stop(now + durationMs / 1000 + 0.05)
  }

  /**
   * 播放柔和通知音（triangle 波形 + 淡出包络）。
   * @param frequency  频率（Hz）
   * @param durationMs 持续时间（毫秒）
   * @param vol        峰值音量，默认 0.12
   */
  function playTone(frequency: number, durationMs: number, vol = 0.12) {
    if (ctx.state === 'suspended') {
      ctx.resume()
    }
    const osc = ctx.createOscillator()
    const envelope = ctx.createGain()
    osc.type = 'triangle'
    osc.frequency.value = frequency
    envelope.gain.value = vol
    const now = ctx.currentTime
    envelope.gain.setValueAtTime(vol, now)
    envelope.gain.exponentialRampToValueAtTime(0.001, now + durationMs / 1000)
    osc.connect(envelope)
    envelope.connect(gain)
    osc.start(now)
    osc.stop(now + durationMs / 1000 + 0.05)
  }

  onBeforeUnmount(() => {
    stopWatch()
    refCount--
    if (refCount <= 0) {
      audioCtx?.close()
      audioCtx = null
      masterGain = null
      refCount = 0
    }
  })

  return { playBeep, playTone }
}
