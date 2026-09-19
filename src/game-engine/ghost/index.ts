import type { SelectionEvent } from '../types'

/**
 * Ghost comparison: how many correct picks had the stored best run made by
 * a given elapsed time, versus the live run right now. Pure function over
 * the stored event timeline — no UI, no timers — so it can run every frame
 * cheaply and stay in sync with a replay for testing.
 */
export interface GhostComparison {
  ghostProgress: number
  liveProgress: number
  delta: number
  status: 'ahead' | 'behind' | 'tied'
}

export function compareToGhost(ghostEvents: SelectionEvent[], elapsedMs: number, liveCorrectCount: number): GhostComparison {
  const ghostProgress = ghostEvents.filter((e) => e.correct && e.timestampMs <= elapsedMs).length
  const delta = liveCorrectCount - ghostProgress
  const status = delta > 0 ? 'ahead' : delta < 0 ? 'behind' : 'tied'
  return { ghostProgress, liveProgress: liveCorrectCount, delta, status }
}
