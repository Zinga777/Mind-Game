import { getDb } from '../data/db'
import { newId, dateKey } from '../data/ids'
import type { GameAttemptRecord, GhostRunRecord, PersonalBestRecord, StreakRecord } from '../data/db'
import type { GameConfig, ObjectiveType, ScoreBreakdown, SelectionEvent } from '../game-engine/types'

function updateStreakForPlay(existing: StreakRecord | undefined, playedAtMs: number): StreakRecord {
  const today = dateKey(playedAtMs)
  if (existing?.lastPlayedDateKey === today) {
    return existing
  }
  const yesterday = dateKey(playedAtMs - 24 * 60 * 60 * 1000)
  const isConsecutive = existing?.lastPlayedDateKey === yesterday
  const current = isConsecutive ? (existing?.current ?? 0) + 1 : 1
  const longest = Math.max(existing?.longest ?? 0, current)
  return { id: 'singleton', current, longest, lastPlayedDateKey: today }
}

export interface RecordAttemptInput {
  config: GameConfig
  events: SelectionEvent[]
  score: ScoreBreakdown
  thunderEarned: number
}

export interface RecordAttemptResult {
  attempt: GameAttemptRecord
  isPersonalBest: boolean
  previousBest: number | null
  streak: StreakRecord
}

export const GameHistoryRepository = {
  async recordAttempt(input: RecordAttemptInput): Promise<RecordAttemptResult> {
    const db = await getDb()
    const playedAt = Date.now()
    const objective = input.config.objective

    const existingPb = await db.get('personalBests', objective)
    const isPersonalBest = !existingPb || input.score.finalScore > existingPb.bestScore

    const attempt: GameAttemptRecord = {
      id: newId('attempt'),
      config: input.config,
      events: input.events,
      score: input.score,
      isPersonalBest,
      thunderEarned: input.thunderEarned,
      playedAt,
    }
    await db.put('gameHistory', attempt)

    if (isPersonalBest) {
      const pb: PersonalBestRecord = {
        objective,
        bestScore: input.score.finalScore,
        attemptId: attempt.id,
        achievedAt: playedAt,
      }
      await db.put('personalBests', pb)

      const ghost: GhostRunRecord = {
        objective,
        config: input.config,
        events: input.events,
        finalScore: input.score.finalScore,
        recordedAt: playedAt,
      }
      await db.put('ghostRuns', ghost)
    }

    const existingStreak = await db.get('streak', 'singleton')
    const streak = updateStreakForPlay(existingStreak, playedAt)
    await db.put('streak', streak)

    return { attempt, isPersonalBest, previousBest: existingPb?.bestScore ?? null, streak }
  },

  async updateThunderEarned(attemptId: string, thunderEarned: number): Promise<void> {
    const db = await getDb()
    const attempt = await db.get('gameHistory', attemptId)
    if (!attempt) return
    await db.put('gameHistory', { ...attempt, thunderEarned })
  },

  async getPersonalBest(objective: ObjectiveType): Promise<PersonalBestRecord | undefined> {
    const db = await getDb()
    return db.get('personalBests', objective)
  },

  async getAllPersonalBests(): Promise<PersonalBestRecord[]> {
    const db = await getDb()
    return db.getAll('personalBests')
  },

  async getGhost(objective: ObjectiveType): Promise<GhostRunRecord | undefined> {
    const db = await getDb()
    return db.get('ghostRuns', objective)
  },

  async getStreak(): Promise<StreakRecord> {
    const db = await getDb()
    return (await db.get('streak', 'singleton')) ?? { id: 'singleton', current: 0, longest: 0, lastPlayedDateKey: null }
  },

  async getRecent(limit = 20): Promise<GameAttemptRecord[]> {
    const db = await getDb()
    const all = await db.getAllFromIndex('gameHistory', 'byPlayedAt')
    return all.reverse().slice(0, limit)
  },

  async getAll(): Promise<GameAttemptRecord[]> {
    const db = await getDb()
    return db.getAll('gameHistory')
  },

  async count(): Promise<number> {
    const db = await getDb()
    return db.count('gameHistory')
  },
}
