import { confusableCandidates } from '../core/gridGenerator'
import type { SelectionEvent } from '../types'

/**
 * Millisecond-precision reaction statistics from a run's event log. Every
 * timestamp in `SelectionEvent` comes from `performance.now()` (see
 * useMindGridSession), never wall-clock time, so these numbers are stable
 * even if the system clock jumps mid-run.
 */
export interface ReactionStats {
  fastestMs: number
  slowestMs: number
  medianMs: number
  meanMs: number
  varianceMs: number
}

const EMPTY_STATS: ReactionStats = { fastestMs: 0, slowestMs: 0, medianMs: 0, meanMs: 0, varianceMs: 0 }

export function computeReactionStats(events: SelectionEvent[]): ReactionStats {
  const reactions = events.filter((e) => e.correct).map((e) => e.reactionMs)
  if (reactions.length === 0) return EMPTY_STATS

  const sorted = [...reactions].sort((a, b) => a - b)
  const mean = sorted.reduce((s, v) => s + v, 0) / sorted.length
  const variance = sorted.reduce((s, v) => s + (v - mean) ** 2, 0) / sorted.length
  const mid = Math.floor(sorted.length / 2)
  const median = sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid]

  return { fastestMs: sorted[0], slowestMs: sorted[sorted.length - 1], medianMs: median, meanMs: mean, varianceMs: variance }
}

/**
 * Turns a mistake into something a player can act on next time, instead of
 * a bare "wrong" — every category here is derived from the actual event
 * log, never invented.
 */
export type MistakeCategory = 'digit-confusion' | 'rushed' | 'other'

export interface MistakeBreakdown {
  total: number
  digitConfusion: number
  rushed: number
  other: number
}

const RUSHED_THRESHOLD_MS = 350

export function classifyMistakes(events: SelectionEvent[], rushedThresholdMs = RUSHED_THRESHOLD_MS): MistakeBreakdown {
  const correctValues = [...new Set(events.filter((e) => e.correct).map((e) => e.value))]
  const incorrect = events.filter((e) => !e.correct)

  let digitConfusion = 0
  let rushed = 0
  let other = 0

  for (const event of incorrect) {
    const isConfusable = correctValues.some((v) => confusableCandidates(v).includes(event.value))
    if (isConfusable) digitConfusion++
    else if (event.reactionMs < rushedThresholdMs) rushed++
    else other++
  }

  return { total: incorrect.length, digitConfusion, rushed, other }
}

/** One deterministic, traceable sentence describing the dominant mistake pattern — or null if there's nothing to say yet. */
export function describeMistakePattern(breakdown: MistakeBreakdown): string | null {
  if (breakdown.total === 0) return null
  if (breakdown.digitConfusion >= Math.ceil(breakdown.total / 2) && breakdown.digitConfusion >= 2) {
    return `${breakdown.digitConfusion} of ${breakdown.total} mistakes were similar-number mix-ups — slow down half a beat on lookalikes.`
  }
  if (breakdown.rushed >= Math.ceil(breakdown.total / 2) && breakdown.rushed >= 2) {
    return `${breakdown.rushed} of ${breakdown.total} mistakes came from picks under ${RUSHED_THRESHOLD_MS}ms — a hair more confirmation would fix most of these.`
  }
  return null
}
