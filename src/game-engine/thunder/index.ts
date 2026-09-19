import type { DifficultyLevel, ScoreBreakdown } from '../types'

/**
 * Thunder is the local, non-cashable resource that gates starting a
 * challenge. Every number here is centralized and swappable — nothing in
 * the game loop hard-codes a cost or reward — so balance can be tuned
 * without touching gameplay code, and so a future server-authoritative
 * economy could apply the same config remotely.
 */
export interface ThunderConfig {
  standardGameCost: number
  hardGameCost: number
  expertGameCost: number
  dailyChallengeCost: number
  rewardedAdAmount: number
  completionReward: number
  pbBonus: number
  accuracyBonus: number
  accuracyBonusThreshold: number
  comboBonus: number
  comboBonusThreshold: number
  achievementBonus: number
  startingBalance: number
}

export const DEFAULT_THUNDER_CONFIG: ThunderConfig = {
  standardGameCost: 10,
  hardGameCost: 15,
  expertGameCost: 20,
  dailyChallengeCost: 0,
  rewardedAdAmount: 40,
  completionReward: 8,
  pbBonus: 25,
  accuracyBonus: 10,
  accuracyBonusThreshold: 0.9,
  comboBonus: 8,
  comboBonusThreshold: 6,
  achievementBonus: 20,
  // Generous enough to play several full games before ever needing an ad —
  // the brief is explicit new players must not hit a paywall immediately.
  startingBalance: 120,
}

export function costForDifficulty(difficulty: DifficultyLevel, config: ThunderConfig = DEFAULT_THUNDER_CONFIG): number {
  if (difficulty === 'beginner' || difficulty === 'intermediate') return config.standardGameCost
  if (difficulty === 'advanced') return config.hardGameCost
  return config.expertGameCost // expert | master
}

export interface ThunderRewardBreakdown {
  completion: number
  accuracy: number
  combo: number
  personalBest: number
  achievements: number
  total: number
}

export function computeThunderReward(
  params: { score: ScoreBreakdown; isPersonalBest: boolean; newAchievementsCount: number },
  config: ThunderConfig = DEFAULT_THUNDER_CONFIG,
): ThunderRewardBreakdown {
  const completion = config.completionReward
  const accuracy = params.score.accuracy >= config.accuracyBonusThreshold ? config.accuracyBonus : 0
  const combo = params.score.bestCombo >= config.comboBonusThreshold ? config.comboBonus : 0
  const personalBest = params.isPersonalBest ? config.pbBonus : 0
  const achievements = params.newAchievementsCount * config.achievementBonus
  return {
    completion,
    accuracy,
    combo,
    personalBest,
    achievements,
    total: completion + accuracy + combo + personalBest + achievements,
  }
}
