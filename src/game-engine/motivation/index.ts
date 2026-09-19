/**
 * Turns the outcome of a completed run into one concrete, traceable reason
 * to play again — never a generic "Good job!". Every field here must come
 * from real stored data (score, PB, ghost timeline); nothing is invented.
 */
export interface RunOutcomeContext {
  finalScore: number
  previousBest: number | null
  isPersonalBest: boolean
  correctCount: number
  /** Known total target count for objectives where it's meaningful (Target Hunt); omit when not applicable. */
  totalTargets?: number
  ghostFinalScore?: number | null
  ghostWasEverAhead?: boolean
  /** Elapsed ms into the run when the player was last ahead of their ghost, if they later fell behind. */
  ghostLeadLostAtMs?: number | null
  durationMs: number
}

export interface OneMoreRunMessage {
  headline: string
  isNearMiss: boolean
}

const NEAR_MISS_PB_RATIO = 0.95
const CLOSE_PB_RATIO = 0.85

export function buildOneMoreRunMessage(ctx: RunOutcomeContext): OneMoreRunMessage {
  if (ctx.isPersonalBest) {
    return { headline: 'New Personal Best', isNearMiss: false }
  }

  if (ctx.previousBest != null && ctx.previousBest > 0) {
    const gap = ctx.previousBest - ctx.finalScore
    const pctOfPb = ctx.finalScore / ctx.previousBest

    if (gap > 0 && pctOfPb >= NEAR_MISS_PB_RATIO) {
      return { headline: `${gap.toLocaleString()} points from your PB — so close`, isNearMiss: true }
    }
    if (gap > 0 && pctOfPb >= CLOSE_PB_RATIO) {
      return { headline: `${gap.toLocaleString()} points from your PB (${Math.round(pctOfPb * 100)}% there)`, isNearMiss: false }
    }
    if (gap > 0) {
      return { headline: `${gap.toLocaleString()} points from your PB`, isNearMiss: false }
    }
  }

  if (ctx.totalTargets != null && ctx.correctCount < ctx.totalTargets) {
    const remaining = ctx.totalTargets - ctx.correctCount
    if (remaining === 1) return { headline: 'One target away', isNearMiss: true }
    return { headline: `${ctx.correctCount}/${ctx.totalTargets} targets found`, isNearMiss: false }
  }

  if (ctx.ghostWasEverAhead && ctx.ghostLeadLostAtMs != null) {
    const secondsRemainingWhenLost = Math.round((ctx.durationMs - ctx.ghostLeadLostAtMs) / 1000)
    if (secondsRemainingWhenLost > 0) {
      return { headline: `Ahead of your ghost until the final ${secondsRemainingWhenLost}s`, isNearMiss: true }
    }
  }

  return { headline: 'Solid run — one more could push your PB', isNearMiss: false }
}
