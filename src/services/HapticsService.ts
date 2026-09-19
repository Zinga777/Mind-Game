/**
 * Thin wrapper over the Vibration API. Falls back to a silent no-op when
 * unsupported (iOS Safari, desktop) — visual/audio feedback already carries
 * the same moment, so haptics are a bonus layer, never load-bearing.
 */

let enabled = true

export function configureHaptics(opts: { enabled: boolean }) {
  enabled = opts.enabled
}

export type HapticKey = 'correct' | 'incorrect' | 'combo' | 'pb' | 'achievement' | 'reward'

const PATTERNS: Record<HapticKey, number | number[]> = {
  correct: 8,
  incorrect: [0, 30, 20, 30],
  combo: 12,
  pb: [0, 40, 30, 40, 30, 60],
  achievement: [0, 30, 20, 30],
  reward: 15,
}

export function playHaptic(key: HapticKey) {
  if (!enabled) return
  if (typeof navigator === 'undefined' || typeof navigator.vibrate !== 'function') return
  navigator.vibrate(PATTERNS[key])
}
