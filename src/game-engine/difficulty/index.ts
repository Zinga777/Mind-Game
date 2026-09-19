import type { DifficultyLevel, MutatorType } from '../types'

export interface DifficultyPreset {
  level: DifficultyLevel
  label: string
  durationSeconds: number
  allowedMutators: MutatorType[]
  scoreMultiplier: number
  wrongTapPenalty: number
  description: string
}

export const DIFFICULTY_PRESETS: Record<DifficultyLevel, DifficultyPreset> = {
  beginner: {
    level: 'beginner',
    label: 'Beginner',
    durationSeconds: 90,
    allowedMutators: [],
    scoreMultiplier: 1,
    wrongTapPenalty: 20,
    description: 'Large targets, simple objective, no mutators.',
  },
  intermediate: {
    level: 'intermediate',
    label: 'Intermediate',
    durationSeconds: 75,
    allowedMutators: ['distraction'],
    scoreMultiplier: 1.25,
    wrongTapPenalty: 35,
    description: 'Shorter timer, light distractors, mild penalties.',
  },
  advanced: {
    level: 'advanced',
    label: 'Advanced',
    durationSeconds: 60,
    allowedMutators: ['shuffle', 'distraction', 'locked-cells', 'moving-targets'],
    scoreMultiplier: 1.5,
    wrongTapPenalty: 50,
    description: 'Shuffle, distraction, multiple rule layers.',
  },
  expert: {
    level: 'expert',
    label: 'Expert',
    durationSeconds: 60,
    allowedMutators: ['shuffle', 'precision', 'distraction', 'rotation', 'mirror', 'locked-cells', 'moving-targets', 'blind-phase'],
    scoreMultiplier: 1.85,
    wrongTapPenalty: 75,
    description: 'Combined mutators, stronger time pressure.',
  },
  master: {
    level: 'master',
    label: 'Master',
    durationSeconds: 45,
    allowedMutators: [
      'shuffle',
      'precision',
      'turbo',
      'vanish',
      'distraction',
      'rotation',
      'mirror',
      'locked-cells',
      'moving-targets',
      'blind-phase',
    ],
    scoreMultiplier: 2.25,
    wrongTapPenalty: 100,
    description: 'Complex mutator combinations, minimal assistance.',
  },
}

export function clampMutatorsToDifficulty(mutators: MutatorType[], difficulty: DifficultyLevel): MutatorType[] {
  const allowed = new Set(DIFFICULTY_PRESETS[difficulty].allowedMutators)
  return mutators.filter((m) => allowed.has(m))
}
