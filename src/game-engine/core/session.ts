import type { CellVisualState, GameConfig, GameSessionState, GridCell } from '../types'
import { generateConfusableGrid, generateGrid, mirrorGridValues, reshuffleGrid, rotateGridValues, swapCellValues } from './gridGenerator'
import { SeededRng } from './rng'
import { createObjectiveState, isRevealPhase, tickMemoryReveal, tickObjective, validateSelection, TARGET_HUNT_COUNT } from '../objectives'
import { resolveMutatorRuntime, validateMutatorCombo } from '../mutators'

/**
 * A session keeps its own RNG stream, seeded from config.seed, so replaying
 * the same seed reproduces the same grid, target order, and mutator timing.
 */
export function createSession(config: GameConfig, nowMs: number): GameSessionState {
  const combo = validateMutatorCombo(config.mutators)
  if (!combo.valid) throw new Error(combo.reason)

  const rng = new SeededRng(config.seed)

  // Target Hunt + Distraction gets a grid built around deliberately
  // confusable near-misses (68/86/69/66/88) rather than just a wider random
  // range — difficulty from genuine visual similarity, not just density.
  const useConfusableGrid = config.objective === 'target-hunt' && config.mutators.includes('distraction')
  const { cells, explicitTargets } = useConfusableGrid
    ? (() => {
        const result = generateConfusableGrid(config, rng, TARGET_HUNT_COUNT)
        return { cells: result.cells, explicitTargets: result.targets }
      })()
    : { cells: generateGrid(config, rng), explicitTargets: undefined }

  const { state: objective, prompt } = createObjectiveState(config.objective, cells, rng, {
    rulePhases: config.rulePhases,
    explicitTargets,
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
    rotationSeq: 0,
    mirrorSeq: 0,
    movingTargetSeq: 0,
    lockedCellSeq: 0,
    lockedCellIds: [],
    blindPhaseSeq: 0,
    blindUntilMs: 0,
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

export function isBlind(state: GameSessionState, elapsedMs: number): boolean {
  return elapsedMs < state.blindUntilMs
}

export function selectCell(state: GameSessionState, cellId: string, nowMs: number): GameSessionState {
  if (state.status !== 'active') return state
  const cell = state.cells.find((c) => c.id === cellId)
  if (!cell) return state
  if (state.cellVisualState[cellId] === 'vanished' || state.cellVisualState[cellId] === 'locked') return state
  if (isRevealPhase(state.objective)) return state
  if (isBlind(state, nowMs - state.startedAtMs)) return state

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

function currentTargetCellId(state: GameSessionState): string | null {
  const objective = state.objective.type === 'rule-switch' ? state.objective.sub : state.objective
  if (objective.type !== 'target-hunt') return null
  const targetValue = objective.targets[objective.index]
  if (targetValue === undefined) return null
  return state.cells.find((c) => c.value === targetValue)?.id ?? null
}

/** Called on each animation/timer frame to advance mutators and reveal phases. */
export function tick(state: GameSessionState, nowMs: number, deltaMs: number): GameSessionState {
  if (state.status !== 'active') return state

  const elapsedMs = nowMs - state.startedAtMs
  let next = state
  const runtime = resolveMutatorRuntime(next.config.mutators, next.config.difficulty)
  const mutators = next.config.mutators

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

  const turboAcceleration = mutators.includes('turbo') ? Math.floor(elapsedMs / 1000) * runtime.turboAccelerationMs : 0

  if (mutators.includes('shuffle')) {
    const interval = Math.max(1500, runtime.shuffleIntervalMs - turboAcceleration)
    const dueSeq = Math.floor(elapsedMs / interval)
    if (dueSeq > next.shuffleSeq) {
      next = { ...next, cells: reshuffleGrid(next.cells, runtimeRng(next, `shuffle:${dueSeq}`)), shuffleSeq: dueSeq }
    }
  }

  if (mutators.includes('rotation')) {
    const interval = Math.max(2000, runtime.rotationIntervalMs - turboAcceleration)
    const dueSeq = Math.floor(elapsedMs / interval)
    if (dueSeq > next.rotationSeq) {
      next = { ...next, cells: rotateGridValues(next.cells, next.config.gridSize), rotationSeq: dueSeq }
    }
  }

  if (mutators.includes('mirror')) {
    const interval = Math.max(2000, runtime.mirrorIntervalMs - turboAcceleration)
    const dueSeq = Math.floor(elapsedMs / interval)
    if (dueSeq > next.mirrorSeq) {
      next = { ...next, cells: mirrorGridValues(next.cells, next.config.gridSize), mirrorSeq: dueSeq }
    }
  }

  if (mutators.includes('moving-targets')) {
    const interval = Math.max(1500, runtime.movingTargetIntervalMs - turboAcceleration)
    const dueSeq = Math.floor(elapsedMs / interval)
    if (dueSeq > next.movingTargetSeq) {
      const targetId = currentTargetCellId(next)
      if (targetId) {
        const rng = runtimeRng(next, `moving-target:${dueSeq}`)
        const otherIds = next.cells.map((c) => c.id).filter((id) => id !== targetId)
        const destination = otherIds[rng.nextInt(0, otherIds.length - 1)]
        next = { ...next, cells: swapCellValues(next.cells, targetId, destination), movingTargetSeq: dueSeq }
      } else {
        next = { ...next, movingTargetSeq: dueSeq }
      }
    }
  }

  if (mutators.includes('locked-cells')) {
    const interval = Math.max(2000, runtime.lockedCellIntervalMs - turboAcceleration)
    const dueSeq = Math.floor(elapsedMs / interval)
    if (dueSeq > next.lockedCellSeq) {
      const rng = runtimeRng(next, `locked:${dueSeq}`)
      const eligible = next.cells.filter((c) => {
        const s = next.cellVisualState[c.id]
        return s === 'idle' || s === 'locked'
      })
      const shuffled = rng.shuffle(eligible.map((c) => c.id))
      const newlyLocked = shuffled.slice(0, Math.min(runtime.lockedCellCount, shuffled.length))

      const nextVisual = { ...next.cellVisualState }
      for (const id of next.lockedCellIds) if (nextVisual[id] === 'locked') nextVisual[id] = 'idle'
      for (const id of newlyLocked) nextVisual[id] = 'locked'

      next = { ...next, cellVisualState: nextVisual, lockedCellIds: newlyLocked, lockedCellSeq: dueSeq }
    }
  }

  if (mutators.includes('blind-phase')) {
    const interval = Math.max(3000, runtime.blindPhaseIntervalMs - turboAcceleration)
    const dueSeq = Math.floor(elapsedMs / interval)
    if (dueSeq > next.blindPhaseSeq) {
      next = { ...next, blindPhaseSeq: dueSeq, blindUntilMs: elapsedMs + runtime.blindPhaseDurationMs }
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
