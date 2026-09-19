export type ProgressionLevel = 'Rookie' | 'Learner' | 'Competitor' | 'Advanced' | 'Expert' | 'Master'

const THRESHOLDS: { level: ProgressionLevel; minScore: number }[] = [
  { level: 'Master', minScore: 300 },
  { level: 'Expert', minScore: 180 },
  { level: 'Advanced', minScore: 100 },
  { level: 'Competitor', minScore: 50 },
  { level: 'Learner', minScore: 20 },
  { level: 'Rookie', minScore: 0 },
]

export interface ProgressionInput {
  totalGames: number
  personalBestCount: number
  averageAccuracy: number // 0-1
}

/**
 * Deterministic progression score — reflects mastery (PBs, accuracy), not
 * raw grind: playing more games alone caps out quickly, while personal
 * bests and consistent accuracy carry real weight.
 */
export function computeProgressionScore(input: ProgressionInput): number {
  const gameContribution = Math.min(input.totalGames * 2, 60)
  const pbContribution = input.personalBestCount * 10
  const accuracyContribution = Math.round(input.averageAccuracy * 50)
  return gameContribution + pbContribution + accuracyContribution
}

export function levelForScore(score: number): ProgressionLevel {
  return THRESHOLDS.find((t) => score >= t.minScore)!.level
}

export function nextLevelThreshold(score: number): { next: ProgressionLevel; pointsToGo: number } | null {
  const sorted = [...THRESHOLDS].sort((a, b) => a.minScore - b.minScore)
  const next = sorted.find((t) => t.minScore > score)
  if (!next) return null
  return { next: next.level, pointsToGo: next.minScore - score }
}
