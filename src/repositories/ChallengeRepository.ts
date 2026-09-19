import { getDb } from '../data/db'
import { dateKey } from '../data/ids'
import type { DailyChallengeRecord } from '../data/db'
import { buildGameConfig } from '../game-engine/core/config'
import { ENGINE_VERSION, type GameConfig } from '../game-engine/types'

const DAILY_OBJECTIVE = 'target-hunt' as const
const DAILY_DIFFICULTY = 'advanced' as const

/**
 * Deterministic date-based seed: the same calendar date + engine version
 * always produces the same challenge for every player, with no server
 * needed to hand it out.
 */
export function buildDailyConfig(date: Date = new Date()): GameConfig {
  const key = dateKey(date.getTime())
  return buildGameConfig({
    objective: DAILY_OBJECTIVE,
    difficulty: DAILY_DIFFICULTY,
    seed: `daily:${key}:${ENGINE_VERSION}`,
  })
}

export const ChallengeRepository = {
  todayKey(): string {
    return dateKey(Date.now())
  },

  async getToday(): Promise<DailyChallengeRecord> {
    const db = await getDb()
    const key = this.todayKey()
    const existing = await db.get('dailyChallenge', key)
    if (existing) return existing
    const fresh: DailyChallengeRecord = {
      dateKey: key,
      attempted: false,
      completed: false,
      score: null,
      isPersonalBest: false,
      attemptId: null,
    }
    return fresh
  },

  async recordCompletion(score: number, isPersonalBest: boolean, attemptId: string): Promise<DailyChallengeRecord> {
    const db = await getDb()
    const record: DailyChallengeRecord = {
      dateKey: this.todayKey(),
      attempted: true,
      completed: true,
      score,
      isPersonalBest,
      attemptId,
    }
    await db.put('dailyChallenge', record)
    return record
  },
}
