import { Router } from 'express'
import { db } from '../db'
import { newId } from '../lib/ids'
import { requireAuth } from '../lib/auth'
import { applyCoinTransaction, getWalletBalance } from '../lib/coins'

export const adsRouter = Router()

const AD_REWARD_COINS = 30
const MAX_REWARDED_ADS_PER_DAY = 5

function dateKey(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

/**
 * Records a completed rewarded-ad view and grants coins. There is no real ad
 * network wired up (see README) — the client shows a simulated "ad" (a timed
 * placeholder, clearly labeled as such) and only calls this once that
 * simulated view finishes. The reward amount and daily cap are decided here,
 * server-side, never by the client.
 */
adsRouter.post('/reward', requireAuth, (req, res) => {
  const userId = req.user!.id
  const placement = String(req.body?.placement ?? 'post_game_reward')

  const todayStart = new Date(dateKey(Date.now())).getTime()
  const countToday = db
    .prepare(`SELECT COUNT(*) as n FROM ad_events WHERE user_id = ? AND status = 'completed' AND created_at >= ?`)
    .get(userId, todayStart) as { n: number }

  if (countToday.n >= MAX_REWARDED_ADS_PER_DAY) {
    db.prepare('INSERT INTO ad_events (id, user_id, placement, status, reward_coins, created_at) VALUES (?, ?, ?, ?, ?, ?)').run(
      newId('ad'),
      userId,
      placement,
      'skipped',
      0,
      Date.now(),
    )
    return res.status(429).json({ error: 'Daily rewarded-ad limit reached', coins: getWalletBalance(userId) })
  }

  const adEventId = newId('ad')
  db.prepare('INSERT INTO ad_events (id, user_id, placement, status, reward_coins, created_at) VALUES (?, ?, ?, ?, ?, ?)').run(
    adEventId,
    userId,
    placement,
    'completed',
    AD_REWARD_COINS,
    Date.now(),
  )
  const coins = applyCoinTransaction(userId, 'EARNED', AD_REWARD_COINS, 'ad_reward', adEventId)

  res.json({ rewardCoins: AD_REWARD_COINS, coins, remainingToday: MAX_REWARDED_ADS_PER_DAY - countToday.n - 1 })
})
