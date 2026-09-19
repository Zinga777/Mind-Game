/**
 * Synthesized SFX via the Web Audio API — no audio asset files to ship or
 * license, and it works offline by construction. Every sound is a short,
 * cheap oscillator envelope, gated by the sound/haptics settings so it
 * never blocks or delays gameplay input.
 */

let ctx: AudioContext | null = null
function getCtx(): AudioContext | null {
  if (typeof window === 'undefined') return null
  if (!ctx) {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctor) return null
    ctx = new Ctor()
  }
  if (ctx.state === 'suspended') ctx.resume()
  return ctx
}

function tone(freq: number, durationMs: number, type: OscillatorType, gainPeak: number, delayMs = 0) {
  const audio = getCtx()
  if (!audio) return
  const osc = audio.createOscillator()
  const gain = audio.createGain()
  osc.type = type
  osc.frequency.value = freq
  const startAt = audio.currentTime + delayMs / 1000
  const stopAt = startAt + durationMs / 1000

  gain.gain.setValueAtTime(0, startAt)
  gain.gain.linearRampToValueAtTime(gainPeak, startAt + 0.008)
  gain.gain.exponentialRampToValueAtTime(0.001, stopAt)

  osc.connect(gain).connect(audio.destination)
  osc.start(startAt)
  osc.stop(stopAt + 0.02)
}

export type SfxKey =
  | 'correct'
  | 'incorrect'
  | 'countdown'
  | 'go'
  | 'combo'
  | 'pb'
  | 'achievement'
  | 'thunder'
  | 'levelUp'
  | 'gameOver'

let masterVolume = 0.7
let enabled = true

export function configureSound(opts: { enabled: boolean; volume: number }) {
  enabled = opts.enabled
  masterVolume = opts.volume
}

export function playSfx(key: SfxKey) {
  if (!enabled) return
  const v = masterVolume

  switch (key) {
    case 'correct':
      tone(880, 90, 'sine', 0.18 * v)
      break
    case 'incorrect':
      tone(160, 140, 'sawtooth', 0.15 * v)
      break
    case 'countdown':
      tone(440, 100, 'square', 0.12 * v)
      break
    case 'go':
      tone(660, 90, 'square', 0.16 * v)
      tone(990, 140, 'square', 0.16 * v, 90)
      break
    case 'combo':
      tone(700, 70, 'triangle', 0.14 * v)
      tone(1050, 90, 'triangle', 0.14 * v, 60)
      break
    case 'pb':
      tone(523, 100, 'triangle', 0.18 * v)
      tone(659, 100, 'triangle', 0.18 * v, 90)
      tone(784, 160, 'triangle', 0.18 * v, 180)
      break
    case 'achievement':
      tone(600, 90, 'sine', 0.16 * v)
      tone(900, 120, 'sine', 0.16 * v, 80)
      break
    case 'thunder':
      tone(1200, 60, 'square', 0.12 * v)
      break
    case 'levelUp':
      tone(440, 90, 'triangle', 0.18 * v)
      tone(554, 90, 'triangle', 0.18 * v, 80)
      tone(659, 90, 'triangle', 0.18 * v, 160)
      tone(880, 180, 'triangle', 0.2 * v, 240)
      break
    case 'gameOver':
      tone(392, 220, 'sine', 0.14 * v)
      break
  }
}
