import type { GameConfig, ScoreBreakdown, SelectionEvent } from '../types'
import { DIFFICULTY_PRESETS } from '../difficulty'
import { resolveMutatorRuntime } from '../mutators'

const SPEED_BONUS_THRESHOLD_MS = 900
const SPEED_BONUS_PER_EVENT = 12
const COMBO_BONUS_PER_STEP = 6
const TIME_BONUS_PER_SECOND_REMAINING = 8

/**
 * Deterministic, explainable scoring. Every field on the returned breakdown
 * sums to `finalScore`, and every input comes from the recorded event log —
 * never from a client-submitted total.
 */
export function computeScore(
  events: SelectionEvent[],
  config: GameConfig,
  remainingTimeMs: number,
  bestCombo: number,
): ScoreBreakdown {
  const preset = DIFFICULTY_PRESETS[config.difficulty]
  const runtime = resolveMutatorRuntime(config.mutators, config.difficulty)

  const correct = events.filter((e) => e.correct)
  const incorrect = events.filter((e) => !e.correct)

  const baseScore = Math.round(correct.length * config.scoring.basePoints * preset.scoreMultiplier)

  const speedBonus = config.scoring.speedBonus
    ? correct.reduce((sum, e) => {
        if (e.reactionMs >= SPEED_BONUS_THRESHOLD_MS) return sum
        const factor = 1 - e.reactionMs / SPEED_BONUS_THRESHOLD_MS
        return sum + Math.round(SPEED_BONUS_PER_EVENT * factor * preset.scoreMultiplier)
      }, 0)
    : 0

  const comboBonus = config.scoring.comboEnabled
    ? Math.round(bestCombo * (bestCombo - 1) * 0.5 * COMBO_BONUS_PER_STEP * 0.1 * preset.scoreMultiplier)
    : 0

  const timeBonus = Math.round((remainingTimeMs / 1000) * TIME_BONUS_PER_SECOND_REMAINING)

  const penaltyPerMistake = config.scoring.wrongTapPenalty * runtime.precisionPenaltyMultiplier
  const penalties = Math.round(incorrect.length * penaltyPerMistake)

  const finalScore = Math.max(0, baseScore + speedBonus + comboBonus + timeBonus - penalties)

  const totalAttempts = events.length
  const accuracy = totalAttempts === 0 ? 0 : correct.length / totalAttempts
  const avgReactionMs =
    correct.length === 0 ? 0 : Math.round(correct.reduce((s, e) => s + e.reactionMs, 0) / correct.length)

  return {
    baseScore,
    speedBonus,
    comboBonus,
    timeBonus,
    penalties,
    finalScore,
    accuracy,
    avgReactionMs,
    correctCount: correct.length,
    incorrectCount: incorrect.length,
    bestCombo,
  }
}
