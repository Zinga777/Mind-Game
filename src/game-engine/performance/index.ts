import type { DifficultyLevel, MutatorType, ObjectiveType, ScoreBreakdown } from '../types'

/**
 * PerformanceAnalyzer — deterministic, rule-based gameplay statistics.
 *
 * This computes game-performance metrics from a player's own history using
 * fixed formulas, nothing more. It is explicitly NOT an AI model and NOT a
 * medical, psychological, or IQ assessment — every number here is a
 * reproducible function of recorded scores, reaction times, and mistakes.
 * Treat "Mind DNA" as a game stats page, not a diagnostic.
 */

export interface AttemptSample {
  objective: ObjectiveType
  difficulty: DifficultyLevel
  mutators: MutatorType[]
  score: ScoreBreakdown
  playedAt: number
}

export type MindDnaMetric = 'speed' | 'accuracy' | 'focus' | 'memory' | 'flexibility' | 'precision'

export type Archetype = 'Sprinter' | 'Scanner' | 'Strategist' | 'Calculator' | 'Adapter' | 'All-Rounder'

export interface MindDnaResult {
  metrics: Record<MindDnaMetric, number>
  strongest: MindDnaMetric
  improvementArea: MindDnaMetric
  archetype: Archetype
  sampleSize: number
}

const METRIC_ARCHETYPE: Record<MindDnaMetric, Archetype> = {
  speed: 'Sprinter',
  focus: 'Scanner',
  memory: 'Strategist',
  flexibility: 'Adapter',
  accuracy: 'Calculator',
  precision: 'Calculator',
}

function clamp(n: number, min = 0, max = 100): number {
  return Math.max(min, Math.min(max, n))
}

function mean(values: number[]): number {
  return values.length === 0 ? 0 : values.reduce((s, v) => s + v, 0) / values.length
}

function stddev(values: number[]): number {
  if (values.length < 2) return 0
  const m = mean(values)
  return Math.sqrt(mean(values.map((v) => (v - m) ** 2)))
}

const DEFAULT_METRICS: Record<MindDnaMetric, number> = {
  speed: 50,
  accuracy: 50,
  focus: 50,
  memory: 50,
  flexibility: 50,
  precision: 50,
}

export function analyzeMindDna(samples: AttemptSample[]): MindDnaResult {
  if (samples.length === 0) {
    return { metrics: DEFAULT_METRICS, strongest: 'accuracy', improvementArea: 'speed', archetype: 'All-Rounder', sampleSize: 0 }
  }

  const accuracies = samples.map((s) => s.score.accuracy)
  const reactions = samples.filter((s) => s.score.avgReactionMs > 0).map((s) => s.score.avgReactionMs)
  const errorRates = samples.map((s) => {
    const total = s.score.correctCount + s.score.incorrectCount
    return total === 0 ? 0 : s.score.incorrectCount / total
  })

  const memorySamples = samples.filter((s) => s.objective === 'memory' || (s.mutators as MutatorType[]).includes('blind-phase'))
  const flexibilitySamples = samples.filter((s) => s.objective === 'rule-switch' || s.mutators.length > 0)

  // Speed: faster average reaction → higher score. 250ms ≈ 95, 1500ms ≈ 15.
  const avgReaction = mean(reactions)
  const speed = reactions.length === 0 ? 50 : clamp(Math.round(100 - (avgReaction - 250) / 13))

  const accuracy = clamp(Math.round(mean(accuracies) * 100))

  // Focus: consistency of accuracy across runs — low variance → high focus.
  const accuracyStdDev = stddev(accuracies)
  const focus = clamp(Math.round(100 - accuracyStdDev * 220))

  const memory = memorySamples.length === 0 ? Math.round(accuracy * 0.85) : clamp(Math.round(mean(memorySamples.map((s) => s.score.accuracy)) * 100))

  const flexibility =
    flexibilitySamples.length === 0 ? Math.round(accuracy * 0.85) : clamp(Math.round(mean(flexibilitySamples.map((s) => s.score.accuracy)) * 100))

  const precision = clamp(Math.round(100 - mean(errorRates) * 100))

  const metrics: Record<MindDnaMetric, number> = { speed, accuracy, focus, memory, flexibility, precision }

  const entries = Object.entries(metrics) as [MindDnaMetric, number][]
  const sorted = [...entries].sort((a, b) => b[1] - a[1])
  const strongest = sorted[0][0]
  const improvementArea = sorted[sorted.length - 1][0]
  const spread = sorted[0][1] - sorted[1][1]
  const archetype: Archetype = spread < 8 ? 'All-Rounder' : METRIC_ARCHETYPE[strongest]

  return { metrics, strongest, improvementArea, archetype, sampleSize: samples.length }
}

export const METRIC_LABEL: Record<MindDnaMetric, string> = {
  speed: 'Speed',
  accuracy: 'Accuracy',
  focus: 'Focus',
  memory: 'Memory',
  flexibility: 'Flexibility',
  precision: 'Precision',
}

/**
 * Deterministic, templated insight strings comparing the latest run against
 * the rolling average of the runs before it. No model, no randomness.
 */
export function generateInsights(samples: AttemptSample[]): string[] {
  if (samples.length === 0) return ['Play your first Mind Grid to start building your profile.']
  if (samples.length === 1) return ["First run logged — play a few more to see trends and your Mind DNA take shape."]

  const [latest, ...rest] = samples
  const priorAccuracy = mean(rest.map((s) => s.score.accuracy))
  const priorReaction = mean(rest.filter((s) => s.score.avgReactionMs > 0).map((s) => s.score.avgReactionMs))
  const priorScore = mean(rest.map((s) => s.score.finalScore))

  const insights: string[] = []

  if (priorAccuracy > 0) {
    const deltaPct = Math.round((latest.score.accuracy - priorAccuracy) * 100)
    if (Math.abs(deltaPct) >= 3) {
      insights.push(
        deltaPct > 0
          ? `Accuracy is up ${deltaPct}% versus your recent average.`
          : `Accuracy dipped ${Math.abs(deltaPct)}% versus your recent average.`,
      )
    }
  }

  if (priorReaction > 0 && latest.score.avgReactionMs > 0) {
    const deltaMs = Math.round(priorReaction - latest.score.avgReactionMs)
    if (Math.abs(deltaMs) >= 40) {
      insights.push(
        deltaMs > 0
          ? `Reaction time improved by ${deltaMs}ms compared to your recent runs.`
          : `Reaction time slowed by ${Math.abs(deltaMs)}ms compared to your recent runs.`,
      )
    }
  }

  if (priorScore > 0) {
    const deltaPct = Math.round(((latest.score.finalScore - priorScore) / priorScore) * 100)
    if (Math.abs(deltaPct) >= 5) {
      insights.push(deltaPct > 0 ? `Score is trending up, ${deltaPct}% above your recent average.` : `Score is ${Math.abs(deltaPct)}% below your recent average — same challenge, next attempt.`)
    }
  }

  const mutatorRuns = rest.filter((s) => s.mutators.length > 0)
  if (latest.mutators.length > 0 && mutatorRuns.length >= 2) {
    const mutatorAccuracy = mean(mutatorRuns.map((s) => s.score.accuracy))
    if (latest.score.accuracy > mutatorAccuracy + 0.05) {
      insights.push('You handle active mutators better than your average — adaptability is a strength.')
    }
  }

  if (insights.length === 0) insights.push('Performance is holding steady versus your recent runs.')
  return insights.slice(0, 3)
}
