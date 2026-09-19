import type { CellVisualState, GameConfig, GameSessionState, GridCell } from '../types'
import { generateGrid, reshuffleGrid } from './gridGenerator'
import { SeededRng } from './rng'
import { createObjectiveState, isRevealPhase, tickMemoryReveal, tickObjective, validateSelection } from '../objectives'
import { resolveMutatorRuntime, validateMutatorCombo } from '../mutators'

/**
 * A session keeps its own RNG stream, seeded from config.seed, so replaying
 * the same seed reproduces the same grid, target order, and shuffle timing.
 */
export function createSession(config: GameConfig, nowMs: number): GameSessionState {
  const combo = validateMutatorCombo(config.mutators)
  if (!combo.valid) throw new Error(combo.reason)

  const rng = new SeededRng(config.seed)
  const cells = generateGrid(config, rng)
  const { state: objective, prompt } = createObjectiveState(config.objective, cells, rng, {
    rulePhases: config.rulePhases,
  })

  const cellVisualState: Record<string, CellVisualState> = {}
  for (const cell of cells) cellVisualState[cell.id] = 'idle'

  return {
    config,
    startedAtMs: nowMs,
    cells,
    cellVisualState,
    objective,
    prompt,
    events: [],
    combo: 0,
    bestCombo: 0,
    correctCount: 0,
    incorrectCount: 0,
    lastEventAtMs: nowMs,
    status: 'active',
    shuffleSeq: 0,
  }
}

/**
 * Runtime RNG streams are re-derived from the session seed plus a deterministic
 * cursor (phase index, shuffle tick count) rather than carried as mutable
 * state, so replaying the same seed always reproduces the same run
 * regardless of exact frame timing.
 */
function runtimeRng(state: GameSessionState, cursor: string): SeededRng {
  return new SeededRng(`${state.config.seed}:${cursor}`)
}

export function selectCell(state: GameSessionState, cellId: string, nowMs: number): GameSessionState {
  if (state.status !== 'active') return state
  const cell = state.cells.find((c) => c.id === cellId)
  if (!cell) return state
  if (state.cellVisualState[cellId] === 'vanished' || state.cellVisualState[cellId] === 'locked') return state
  if (isRevealPhase(state.objective)) return state

  const result = validateSelection(state.objective, cell)
  const reactionMs = Math.max(0, nowMs - state.lastEventAtMs)

  const nextCombo = result.correct ? state.combo + 1 : 0
  const nextVisual: Record<string, CellVisualState> = {
    ...state.cellVisualState,
    [cellId]: result.correct ? 'correct' : 'incorrect',
  }

  const next: GameSessionState = {
    ...state,
    objective: result.state,
    prompt: result.prompt,
    events: [...state.events, { cellId, value: cell.value, correct: result.correct, timestampMs: nowMs, reactionMs }],
    combo: nextCombo,
    bestCombo: Math.max(state.bestCombo, nextCombo),
    correctCount: state.correctCount + (result.correct ? 1 : 0),
    incorrectCount: state.incorrectCount + (result.correct ? 0 : 1),
    lastEventAtMs: nowMs,
    cellVisualState: nextVisual,
    status: result.completed ? 'completed' : state.status,
  }

  if (result.correct && state.config.mutators.includes('vanish')) {
    next.cellVisualState = { ...next.cellVisualState, [cellId]: 'vanished' }
  }

  return next
}

/** Called on each animation/timer frame to advance mutators and reveal phases. */
export function tick(state: GameSessionState, nowMs: number, deltaMs: number): GameSessionState {
  if (state.status !== 'active') return state

  const elapsedMs = nowMs - state.startedAtMs
  let next = state

  const { state: objAfterRuleSwitch, prompt } = tickObjective(
    next.objective,
    elapsedMs,
    next.cells,
    runtimeRng(next, `phase:${next.objective.type === 'rule-switch' ? next.objective.activePhaseIndex + 1 : 0}`),
  )
  if (objAfterRuleSwitch !== next.objective) {
    next = { ...next, objective: objAfterRuleSwitch, prompt }
  }

  const revealedObjective = tickMemoryReveal(next.objective, deltaMs)
  if (revealedObjective !== next.objective) {
    const stillRevealing = isRevealPhase(revealedObjective)
    next = {
      ...next,
      objective: revealedObjective,
      prompt: stillRevealing ? next.prompt : next.prompt.replace('MEMORIZE', 'RECALL'),
    }
  }

  if (next.config.mutators.includes('shuffle')) {
    const runtime = resolveMutatorRuntime(next.config.mutators, next.config.difficulty)
    const acceleration = next.config.mutators.includes('turbo')
      ? Math.floor(elapsedMs / 1000) * 250
      : 0
    const interval = Math.max(1500, runtime.shuffleIntervalMs - acceleration)
    const dueSeq = Math.floor(elapsedMs / interval)
    if (dueSeq > next.shuffleSeq) {
      const reshuffled = reshuffleGrid(next.cells, runtimeRng(next, `shuffle:${dueSeq}`))
      next = { ...next, cells: reshuffled, shuffleSeq: dueSeq }
    }
  }

  const durationMs = next.config.durationSeconds * 1000
  if (elapsedMs >= durationMs) {
    next = { ...next, status: 'completed' }
  }

  return next
}

export function remainingTimeMs(state: GameSessionState, nowMs: number): number {
  const durationMs = state.config.durationSeconds * 1000
  const elapsed = nowMs - state.startedAtMs
  return Math.max(0, durationMs - elapsed)
}

export function cellById(cells: GridCell[], id: string): GridCell | undefined {
  return cells.find((c) => c.id === id)
}
