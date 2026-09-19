import { Router } from 'express'
import { db } from '../db'
import { requireAuth } from '../lib/auth'
import { getWalletBalance } from '../lib/coins'

export const profileRouter = Router()

profileRouter.get('/', requireAuth, (req, res) => {
  const userId = req.user!.id

  const personalBests = db
    .prepare('SELECT objective, best_score as bestScore FROM personal_bests WHERE user_id = ?')
    .all(userId) as { objective: string; bestScore: number }[]

  const streak = db
    .prepare('SELECT current_streak as current, longest_streak as longest FROM streaks WHERE user_id = ?')
    .get(userId) as { current: number; longest: number } | undefined

  const recentRuns = db
    .prepare('SELECT id, objective, difficulty, final_score as finalScore, played_at as playedAt FROM game_attempts WHERE user_id = ? ORDER BY played_at DESC LIMIT 10')
    .all(userId)

  const totalRuns = db.prepare('SELECT COUNT(*) as n FROM game_attempts WHERE user_id = ?').get(userId) as { n: number }

  res.json({
    user: req.user,
    coins: getWalletBalance(userId),
    personalBests: Object.fromEntries(personalBests.map((p) => [p.objective, p.bestScore])),
    streak: streak ?? { current: 0, longest: 0 },
    recentRuns,
    totalRuns: totalRuns.n,
  })
})
