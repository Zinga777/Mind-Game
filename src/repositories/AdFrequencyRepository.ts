import { getDb } from '../data/db'
import { dateKey } from '../data/ids'
import type { AdFrequencyRecord } from '../data/db'

async function ensure(): Promise<AdFrequencyRecord> {
  const db = await getDb()
  const existing = await db.get('adFrequency', 'singleton')
  if (existing) return existing
  const fresh: AdFrequencyRecord = {
    id: 'singleton',
    gamesSincePlayedTotal: 0,
    gamesSinceLastInterstitial: 0,
    lastInterstitialAt: null,
    rewardedAdsWatchedToday: 0,
    rewardedAdsDayKey: null,
    firstSessionAt: Date.now(),
  }
  await db.put('adFrequency', fresh)
  return fresh
}

export const AdFrequencyRepository = {
  get: ensure,

  async recordGamePlayed(): Promise<AdFrequencyRecord> {
    const db = await getDb()
    const current = await ensure()
    const next: AdFrequencyRecord = {
      ...current,
      gamesSincePlayedTotal: current.gamesSincePlayedTotal + 1,
      gamesSinceLastInterstitial: current.gamesSinceLastInterstitial + 1,
    }
    await db.put('adFrequency', next)
    return next
  },

  async recordInterstitialShown(): Promise<AdFrequencyRecord> {
    const db = await getDb()
    const current = await ensure()
    const next: AdFrequencyRecord = { ...current, gamesSinceLastInterstitial: 0, lastInterstitialAt: Date.now() }
    await db.put('adFrequency', next)
    return next
  },

  async recordRewardedAdWatched(): Promise<AdFrequencyRecord> {
    const db = await getDb()
    const current = await ensure()
    const today = dateKey(Date.now())
    const sameDay = current.rewardedAdsDayKey === today
    const next: AdFrequencyRecord = {
      ...current,
      rewardedAdsDayKey: today,
      rewardedAdsWatchedToday: sameDay ? current.rewardedAdsWatchedToday + 1 : 1,
    }
    await db.put('adFrequency', next)
    return next
  },
}
