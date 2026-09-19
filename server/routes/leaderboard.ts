import { Router } from 'express'
import { db } from '../db'
import { requireAuth } from '../lib/auth'

export const leaderboardRouter = Router()

interface LeaderboardRow {
  rank: number
  userId: string
  displayName: string
  bestScore: number
}

function topScoresByUser(objective: string, difficulty: string, limit: number): LeaderboardRow[] {
  const rows = db
    .prepare(
      `SELECT u.id as userId, u.display_name as displayName, MAX(a.final_score) as bestScore
       FROM game_attempts a JOIN users u ON u.id = a.user_id
       WHERE a.objective = ? AND a.difficulty = ?
       GROUP BY u.id
       ORDER BY bestScore DESC
       LIMIT ?`,
    )
    .all(objective, difficulty, limit) as Omit<LeaderboardRow, 'rank'>[]
  return rows.map((r, i) => ({ ...r, rank: i + 1 }))
}

leaderboardRouter.get('/', requireAuth, (req, res) => {
  const objective = String(req.query.objective ?? 'target-hunt')
  const difficulty = String(req.query.difficulty ?? 'advanced')
  const limit = Math.min(100, Number(req.query.limit ?? 20))

  const top = topScoresByUser(objective, difficulty, limit)

  const myBest = db
    .prepare('SELECT MAX(final_score) as best FROM game_attempts WHERE user_id = ? AND objective = ? AND difficulty = ?')
    .get(req.user!.id, objective, difficulty) as { best: number | null }

  let myRank: number | null = null
  if (myBest.best != null) {
    const better = db
      .prepare(
        `SELECT COUNT(*) as n FROM (
           SELECT user_id, MAX(final_score) as best FROM game_attempts
           WHERE objective = ? AND difficulty = ? GROUP BY user_id
         ) WHERE best > ?`,
      )
      .get(objective, difficulty, myBest.best) as { n: number }
    myRank = better.n + 1
  }

  res.json({ objective, difficulty, top, myBest: myBest.best, myRank })
})
