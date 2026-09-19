/**
 * Mind Grid game engine — shared types.
 *
 * The engine is pure TypeScript with zero UI dependencies. Given the same
 * GameConfig + seed it always produces the same grid and objective sequence,
 * which is required for fair tournaments and reproducible daily challenges.
 */

export const ENGINE_VERSION = '0.1.0'

export type ObjectiveType =
  | 'ascending'
  | 'descending'
  | 'target-hunt'
  | 'min-max'
  | 'odd-even'
  | 'divisibility'
  | 'rule-switch'
  | 'memory'

export type MutatorType = 'shuffle' | 'vanish' | 'precision' | 'turbo' | 'distraction'

export type DifficultyLevel = 'beginner' | 'intermediate' | 'advanced' | 'expert' | 'master'

export interface ScoringConfig {
  basePoints: number
  comboEnabled: boolean
  speedBonus: boolean
  wrongTapPenalty: number
}

export interface GameConfig {
  gameId: 'mind-grid'
  gridSize: number
  numberRange: [number, number]
  objective: ObjectiveType
  /** Only used when objective === 'rule-switch' */
  rulePhases?: { objective: ObjectiveType; durationSeconds: number }[]
  durationSeconds: number
  difficulty: DifficultyLevel
  mutators: MutatorType[]
  scoring: ScoringConfig
  seed: string
  engineVersion: string
}

export interface GridCell {
  id: string
  row: number
  col: number
  value: number
}

export type CellVisualState = 'idle' | 'selected' | 'correct' | 'incorrect' | 'vanished' | 'locked'

export interface ObjectiveResult {
  correct: boolean
  completed: boolean
  prompt: string
}

export type ObjectiveState =
  | { type: 'ascending' | 'descending'; queue: number[] }
  | { type: 'min-max'; mode: 'min' | 'max'; remaining: number[] }
  | { type: 'odd-even'; parity: 'odd' | 'even'; queue: number[] }
  | { type: 'divisibility'; divisor: number; remaining: number[] }
  | { type: 'target-hunt'; targets: number[]; index: number }
  | {
      type: 'memory'
      targets: number[]
      index: number
      revealUntil: number
      revealMs: number
    }
  | {
      type: 'rule-switch'
      phases: { objective: ObjectiveType; startAt: number; endAt: number }[]
      activePhaseIndex: number
      sub: ObjectiveState
    }

export interface SelectionEvent {
  cellId: string
  value: number
  correct: boolean
  timestampMs: number
  reactionMs: number
}

export interface GameSessionState {
  config: GameConfig
  startedAtMs: number
  cells: GridCell[]
  cellVisualState: Record<string, CellVisualState>
  objective: ObjectiveState
  prompt: string
  events: SelectionEvent[]
  combo: number
  bestCombo: number
  correctCount: number
  incorrectCount: number
  lastEventAtMs: number
  status: 'countdown' | 'active' | 'completed'
  shuffleSeq: number
}

export interface ScoreBreakdown {
  baseScore: number
  speedBonus: number
  comboBonus: number
  timeBonus: number
  penalties: number
  finalScore: number
  accuracy: number
  avgReactionMs: number
  correctCount: number
  incorrectCount: number
  bestCombo: number
}
