import { AdFrequencyRepository } from '../repositories/AdFrequencyRepository'
import type { AdFrequencyRecord } from '../data/db'

export interface AdFrequencyConfig {
  minGamesBetweenInterstitials: number
  minTimeBetweenInterstitialsMs: number
  /** Games a brand-new player gets before any interstitial can show at all. */
  newPlayerProtectionGames: number
}

export const DEFAULT_AD_FREQUENCY_CONFIG: AdFrequencyConfig = {
  minGamesBetweenInterstitials: 4,
  minTimeBetweenInterstitialsMs: 5 * 60 * 1000,
  newPlayerProtectionGames: 3,
}

/**
 * Pure decision function — interstitials only at natural transitions
 * (leaving Results, back to Home), gated by game-count cooldown, time
 * cooldown, and new-player protection. The caller is responsible for never
 * invoking this during active gameplay or before the player has seen their
 * results, PB, achievements, and Thunder reward.
 */
export function shouldShowInterstitial(record: AdFrequencyRecord, config: AdFrequencyConfig = DEFAULT_AD_FREQUENCY_CONFIG): boolean {
  if (record.gamesSincePlayedTotal < config.newPlayerProtectionGames) return false
  if (record.gamesSinceLastInterstitial < config.minGamesBetweenInterstitials) return false
  if (record.lastInterstitialAt && Date.now() - record.lastInterstitialAt < config.minTimeBetweenInterstitialsMs) return false
  return true
}

export const AdFrequencyManager = {
  recordGamePlayed: () => AdFrequencyRepository.recordGamePlayed(),
  recordInterstitialShown: () => AdFrequencyRepository.recordInterstitialShown(),
  recordRewardedAdWatched: () => AdFrequencyRepository.recordRewardedAdWatched(),

  async checkInterstitialEligibility(config?: AdFrequencyConfig): Promise<boolean> {
    const record = await AdFrequencyRepository.get()
    return shouldShowInterstitial(record, config)
  },
}
