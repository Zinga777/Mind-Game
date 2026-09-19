import type { AttemptSample } from '../performance'

export interface AchievementDefinition {
  id: string
  title: string
  description: string
}

export const ACHIEVEMENTS: AchievementDefinition[] = [
  { id: 'first-step', title: 'First Step', description: 'Complete your first Mind Grid.' },
  { id: 'speedster', title: 'Speedster', description: 'Average under 400ms reaction time on a 10+ pick run.' },
  { id: 'precision', title: 'Precision', description: 'Finish a run with 99%+ accuracy.' },
  { id: 'pb-breaker', title: 'PB Breaker', description: 'Beat your personal best 10 times.' },
  { id: 'no-mistakes', title: 'No Mistakes', description: 'Finish a run of 5+ picks with zero mistakes.' },
  { id: 'memory-builder', title: 'Memory Builder', description: 'Score 90%+ accuracy on a Memory Grid run.' },
  { id: 'adapter', title: 'Adapter', description: 'Score 70%+ accuracy on a run with 2+ active mutators.' },
  { id: 'grid-master', title: 'Grid Master', description: 'Reach the Master progression level.' },
]

export interface AchievementContext {
  latest: AttemptSample
  history: AttemptSample[] // includes latest, most recent first
  progressionLevel: string
}

/** Pure rule checks — same input always yields the same unlocked set. */
export function evaluateAchievements(ctx: AchievementContext): string[] {
  const unlocked: string[] = []
  const { latest, history } = ctx
  const totalPicks = latest.score.correctCount + latest.score.incorrectCount

  if (history.length >= 1) unlocked.push('first-step')

  if (latest.score.avgReactionMs > 0 && latest.score.avgReactionMs < 400 && latest.score.correctCount >= 10) {
    unlocked.push('speedster')
  }

  if (latest.score.accuracy >= 0.99 && totalPicks >= 5) {
    unlocked.push('precision')
  }

  if (latest.score.incorrectCount === 0 && latest.score.correctCount >= 5) {
    unlocked.push('no-mistakes')
  }

  if (latest.objective === 'memory' && latest.score.accuracy >= 0.9) {
    unlocked.push('memory-builder')
  }

  if (latest.mutators.length >= 2 && latest.score.accuracy >= 0.7) {
    unlocked.push('adapter')
  }

  if (ctx.progressionLevel === 'Master') {
    unlocked.push('grid-master')
  }

  return unlocked
}

/** Separate check since it needs the count of PB-flagged attempts across history, supplied by the caller (repository knows this; the engine doesn't). */
export function checkPbBreaker(personalBestAttemptCount: number): boolean {
  return personalBestAttemptCount >= 10
}
