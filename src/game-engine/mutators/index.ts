import type { DifficultyLevel, MutatorType } from '../types'

/** Mutators that cannot be combined, because they'd fight over the same mechanic. */
const INCOMPATIBLE_PAIRS: [MutatorType, MutatorType][] = [['shuffle', 'vanish']]

export function validateMutatorCombo(mutators: MutatorType[]): { valid: boolean; reason?: string } {
  for (const [a, b] of INCOMPATIBLE_PAIRS) {
    if (mutators.includes(a) && mutators.includes(b)) {
      return { valid: false, reason: `"${a}" and "${b}" cannot be combined — both control cell layout.` }
    }
  }
  return { valid: true }
}

export interface MutatorRuntimeConfig {
  /** ms between grid reshuffles, if `shuffle` is active */
  shuffleIntervalMs: number
  /** multiplier applied to wrongTapPenalty, if `precision` is active */
  precisionPenaltyMultiplier: number
  /** how much shuffleIntervalMs shrinks per elapsed second, if `turbo` is active */
  turboAccelerationMs: number
  /** ms a correctly-selected cell stays visible before vanishing, if `vanish` is active */
  vanishDelayMs: number
  /** widens numberRange for target-hunt to raise digit-collision distractors */
  distractionRangeMultiplier: number
}

const BASE_RUNTIME: MutatorRuntimeConfig = {
  shuffleIntervalMs: 8000,
  precisionPenaltyMultiplier: 1,
  turboAccelerationMs: 0,
  vanishDelayMs: 400,
  distractionRangeMultiplier: 1,
}

export function resolveMutatorRuntime(mutators: MutatorType[], difficulty: DifficultyLevel): MutatorRuntimeConfig {
  const config = { ...BASE_RUNTIME }
  const difficultyFactor = { beginner: 1.4, intermediate: 1.2, advanced: 1, expert: 0.85, master: 0.7 }[difficulty]

  if (mutators.includes('shuffle')) {
    config.shuffleIntervalMs = Math.round(7000 * difficultyFactor)
  }
  if (mutators.includes('precision')) {
    config.precisionPenaltyMultiplier = 2.5
  }
  if (mutators.includes('turbo')) {
    config.turboAccelerationMs = 250
  }
  if (mutators.includes('vanish')) {
    config.vanishDelayMs = 350
  }
  if (mutators.includes('distraction')) {
    config.distractionRangeMultiplier = 3
  }
  return config
}
