import { Router } from 'express'
import { db } from '../db'
import { newId } from '../lib/ids'
import { requireAuth } from '../lib/auth'
import { validateAttempt } from '../lib/scoreValidation'
import { applyCoinTransaction, getWalletBalance } from '../lib/coins'
import type { GameConfig, SelectionEvent } from '../../src/game-engine'

export const gameAttemptsRouter = Router()

const PB_REWARD_COINS = 15

function dateKey(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

function updateStreak(userId: string, playedAtMs: number) {
  const today = dateKey(playedAtMs)
  const row = db.prepare('SELECT current_streak as current, longest_streak as longest, last_played_date as lastPlayed FROM streaks WHERE user_id = ?').get(
    userId,
  ) as { current: number; longest: number; lastPlayed: string | null } | undefined

  if (row?.lastPlayed === today) return { current: row.current, longest: row.longest }

  const yesterday = dateKey(playedAtMs - 24 * 60 * 60 * 1000)
  const isConsecutive = row?.lastPlayed === yesterday
  const current = isConsecutive ? (row?.current ?? 0) + 1 : 1
  const longest = Math.max(row?.longest ?? 0, current)

  db.prepare(
    `INSERT INTO streaks (user_id, current_streak, longest_streak, last_played_date) VALUES (?, ?, ?, ?)
     ON CONFLICT(user_id) DO UPDATE SET current_streak = excluded.current_streak, longest_streak = excluded.longest_streak, last_played_date = excluded.last_played_date`,
  ).run(userId, current, longest, today)

  return { current, longest }
}

gameAttemptsRouter.post('/', requireAuth, (req, res) => {
  const userId = req.user!.id
  const body = req.body as { config: GameConfig; events: SelectionEvent[]; remainingTimeMs: number; bestCombo: number }

  if (!body?.config || !Array.isArray(body.events)) {
    return res.status(400).json({ error: 'Malformed attempt payload' })
  }

  const result = validateAttempt(body)
  if (!result.valid || !result.score) {
    return res.status(422).json({ error: result.reason ?? 'Invalid attempt' })
  }

  const score = result.score
  const playedAt = Date.now()
  const attemptId = newId('attempt')

  db.prepare(
    `INSERT INTO game_attempts (
      id, user_id, objective, difficulty, mutators, seed, engine_version,
      final_score, base_score, speed_bonus, combo_bonus, time_bonus, penalties,
      accuracy, avg_reaction_ms, correct_count, incorrect_count, best_combo, played_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    attemptId,
    userId,
    body.config.objective,
    body.config.difficulty,
    JSON.stringify(body.config.mutators),
    body.config.seed,
    body.config.engineVersion,
    score.finalScore,
    score.baseScore,
    score.speedBonus,
    score.comboBonus,
    score.timeBonus,
    score.penalties,
    score.accuracy,
    score.avgReactionMs,
    score.correctCount,
    score.incorrectCount,
    score.bestCombo,
    playedAt,
  )

  const existingPb = db
    .prepare('SELECT best_score as bestScore FROM personal_bests WHERE user_id = ? AND objective = ?')
    .get(userId, body.config.objective) as { bestScore: number } | undefined

  const isNewPersonalBest = !existingPb || score.finalScore > existingPb.bestScore
  if (isNewPersonalBest) {
    db.prepare(
      `INSERT INTO personal_bests (user_id, objective, best_score, attempt_id, achieved_at) VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(user_id, objective) DO UPDATE SET best_score = excluded.best_score, attempt_id = excluded.attempt_id, achieved_at = excluded.achieved_at`,
    ).run(userId, body.config.objective, score.finalScore, attemptId, playedAt)
    applyCoinTransaction(userId, 'EARNED', PB_REWARD_COINS, 'personal_best', attemptId)
  }

  const streak = updateStreak(userId, playedAt)

  const rankRow = db
    .prepare(
      `SELECT COUNT(*) + 1 as rank FROM (
         SELECT user_id, MAX(final_score) as best FROM game_attempts
         WHERE objective = ? AND difficulty = ? GROUP BY user_id
       ) WHERE best > ?`,
    )
    .get(body.config.objective, body.config.difficulty, score.finalScore) as { rank: number }

  res.json({
    attemptId,
    score,
    isNewPersonalBest,
    previousBest: existingPb?.bestScore ?? null,
    streak,
    coins: getWalletBalance(userId),
    globalRank: rankRow.rank,
  })
})

gameAttemptsRouter.get('/mine', requireAuth, (req, res) => {
  const rows = db
    .prepare('SELECT * FROM game_attempts WHERE user_id = ? ORDER BY played_at DESC LIMIT 50')
    .all(req.user!.id)
  res.json({ attempts: rows })
})
