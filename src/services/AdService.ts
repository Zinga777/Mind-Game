/**
 * Ad provider abstraction. No caller talks to a network SDK directly — they
 * go through this interface, so swapping in a real ad network later means
 * writing one new class, not touching every call site.
 */
export interface AdService {
  isRewardedAdAvailable(): Promise<boolean>
  /** Resolves with the reward amount if the ad was watched to completion, or null if skipped/failed/unavailable. */
  showRewardedThunderAd(): Promise<{ watched: boolean }>
  isInterstitialAvailable(): Promise<boolean>
  showInterstitial(): Promise<{ shown: boolean }>
}

/**
 * Local development / V1 implementation: no real network SDK is wired up.
 * Rewarded ads are "available" whenever the device is online (a real SDK
 * would report the same for a genuinely empty ad fill), and "showing" one
 * is a UI concern (see RewardedAdModal) — this class only reports
 * availability and completion, matching what a real SDK's async API shape
 * looks like.
 */
export class MockAdService implements AdService {
  async isRewardedAdAvailable(): Promise<boolean> {
    return navigator.onLine
  }

  async showRewardedThunderAd(): Promise<{ watched: boolean }> {
    // Actual playback happens in RewardedAdModal; this method exists so a
    // real SDK integration has a natural drop-in point. The mock always
    // resolves "watched" here since the UI component gates completion.
    return { watched: navigator.onLine }
  }

  async isInterstitialAvailable(): Promise<boolean> {
    return navigator.onLine
  }

  async showInterstitial(): Promise<{ shown: boolean }> {
    return { shown: navigator.onLine }
  }
}

export const adService: AdService = new MockAdService()
