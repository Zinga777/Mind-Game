import type { DifficultyLevel, MutatorType } from '../types'

/** Mutators that cannot be combined, because they'd fight over the same mechanic. */
const INCOMPATIBLE_PAIRS: [MutatorType, MutatorType][] = [
  ['shuffle', 'vanish'],
  ['shuffle', 'rotation'],
  ['shuffle', 'mirror'],
  ['rotation', 'mirror'],
]

export function validateMutatorCombo(mutators: MutatorType[]): { valid: boolean; reason?: string } {
  for (const [a, b] of INCOMPATIBLE_PAIRS) {
    if (mutators.includes(a) && mutators.includes(b)) {
      return { valid: false, reason: `"${a}" and "${b}" cannot be combined — both control cell layout.` }
    }
  }
  return { valid: true }
}

/** Drops later mutators that conflict with an earlier one, so a config is always launchable. */
export function resolveCompatibleMutators(mutators: MutatorType[]): MutatorType[] {
  const resolved: MutatorType[] = []
  for (const m of mutators) {
    const conflicts = INCOMPATIBLE_PAIRS.some(
      ([a, b]) => (a === m && resolved.includes(b)) || (b === m && resolved.includes(a)),
    )
    if (!conflicts) resolved.push(m)
  }
  return resolved
}

export interface MutatorRuntimeConfig {
  /** ms between grid reshuffles, if `shuffle` is active */
  shuffleIntervalMs: number
  /** multiplier applied to wrongTapPenalty, if `precision` is active */
  precisionPenaltyMultiplier: number
  /** how much interval-based mutators accelerate per elapsed second, if `turbo` is active */
  turboAccelerationMs: number
  /** ms a correctly-selected cell stays visible before vanishing, if `vanish` is active */
  vanishDelayMs: number
  /** widens numberRange for target-hunt to raise digit-collision distractors */
  distractionRangeMultiplier: number
  /** ms between 90° value rotations, if `rotation` is active */
  rotationIntervalMs: number
  /** ms between horizontal mirrors, if `mirror` is active */
  mirrorIntervalMs: number
  /** ms between the active target relocating, if `moving-targets` is active */
  movingTargetIntervalMs: number
  /** ms between a new set of cells locking, if `locked-cells` is active */
  lockedCellIntervalMs: number
  /** how long a locked cell stays unselectable */
  lockedCellDurationMs: number
  /** how many cells lock at once */
  lockedCellCount: number
  /** ms between blind phases, if `blind-phase` is active */
  blindPhaseIntervalMs: number
  /** how long the grid stays hidden during a blind phase */
  blindPhaseDurationMs: number
}

const BASE_RUNTIME: MutatorRuntimeConfig = {
  shuffleIntervalMs: 8000,
  precisionPenaltyMultiplier: 1,
  turboAccelerationMs: 0,
  vanishDelayMs: 400,
  distractionRangeMultiplier: 1,
  rotationIntervalMs: 9000,
  mirrorIntervalMs: 9000,
  movingTargetIntervalMs: 4000,
  lockedCellIntervalMs: 6000,
  lockedCellDurationMs: 2500,
  lockedCellCount: 6,
  blindPhaseIntervalMs: 10000,
  blindPhaseDurationMs: 1200,
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
  if (mutators.includes('rotation')) {
    config.rotationIntervalMs = Math.round(8000 * difficultyFactor)
  }
  if (mutators.includes('mirror')) {
    config.mirrorIntervalMs = Math.round(8000 * difficultyFactor)
  }
  if (mutators.includes('moving-targets')) {
    config.movingTargetIntervalMs = Math.round(3500 * difficultyFactor)
  }
  if (mutators.includes('locked-cells')) {
    config.lockedCellIntervalMs = Math.round(5000 * difficultyFactor)
  }
  if (mutators.includes('blind-phase')) {
    config.blindPhaseIntervalMs = Math.round(9000 * difficultyFactor)
  }
  return config
}
