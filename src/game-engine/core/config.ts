import { DIFFICULTY_PRESETS, clampMutatorsToDifficulty } from '../difficulty'
import { resolveCompatibleMutators, resolveMutatorRuntime } from '../mutators'
import { SeededRng } from './rng'
import { ENGINE_VERSION, type DifficultyLevel, type GameConfig, type MutatorType, type ObjectiveType } from '../types'

export interface BuildGameConfigInput {
  objective: ObjectiveType
  difficulty: DifficultyLevel
  mutators?: MutatorType[]
  seed: string
  gridSize?: number
  durationSeconds?: number
  rulePhases?: GameConfig['rulePhases']
}

/**
 * Builds a fully-specified, versioned GameConfig from high-level choices.
 * This is what the backend would persist for a daily challenge or
 * tournament round so every participant plays the identical config.
 */
export function buildGameConfig(input: BuildGameConfigInput): GameConfig {
  const preset = DIFFICULTY_PRESETS[input.difficulty]
  const requested = input.mutators ?? pickRandomMutatorSubset(preset.allowedMutators, input.seed)
  const clamped = clampMutatorsToDifficulty(requested, input.difficulty)
  const mutators = resolveCompatibleMutators(clamped)
  const runtime = resolveMutatorRuntime(mutators, input.difficulty)
  const gridSize = input.gridSize ?? 10
  const cellCount = gridSize * gridSize

  const baseMax = input.objective === 'target-hunt' || input.objective === 'memory' ? cellCount * runtime.distractionRangeMultiplier : cellCount

  return {
    gameId: 'mind-grid',
    gridSize,
    numberRange: [1, Math.max(cellCount, baseMax)],
    objective: input.objective,
    rulePhases: input.rulePhases,
    durationSeconds: input.durationSeconds ?? preset.durationSeconds,
    difficulty: input.difficulty,
    mutators,
    scoring: {
      basePoints: 10,
      comboEnabled: true,
      speedBonus: true,
      wrongTapPenalty: preset.wrongTapPenalty,
    },
    seed: input.seed,
    engineVersion: ENGINE_VERSION,
  }
}

/**
 * Deterministically picks a varied-but-compatible mutator set from a
 * difficulty's allowed pool, seeded so the same seed always proposes the
 * same set (needed for daily challenges / ghost reproducibility).
 */
function pickRandomMutatorSubset(pool: MutatorType[], seed: string): MutatorType[] {
  if (pool.length === 0) return []
  const rng = new SeededRng(`${seed}:mutator-pick`)
  const shuffled = rng.shuffle(pool)
  const count = Math.min(shuffled.length, 1 + Math.floor(rng.next() * 3))
  return shuffled.slice(0, count)
}

export function randomSeed(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}
