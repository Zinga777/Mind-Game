import type { GridCell, ObjectiveResult, ObjectiveState, ObjectiveType } from '../types'
import { SeededRng } from '../core/rng'

const MEMORY_REVEAL_MS = 2500

function promptFor(state: ObjectiveState): string {
  switch (state.type) {
    case 'ascending':
      return state.queue.length ? `FIND ${state.queue[0]}` : 'COMPLETE'
    case 'descending':
      return state.queue.length ? `FIND ${state.queue[0]}` : 'COMPLETE'
    case 'min-max':
      return state.mode === 'min' ? 'SELECT THE SMALLEST' : 'SELECT THE LARGEST'
    case 'odd-even':
      return `SELECT ${state.parity === 'even' ? 'EVEN' : 'ODD'} NUMBERS, ASCENDING`
    case 'divisibility':
      return `SELECT NUMBERS DIVISIBLE BY ${state.divisor}`
    case 'target-hunt':
      return state.index < state.targets.length ? `FIND ${state.targets[state.index]}` : 'COMPLETE'
    case 'memory':
      return state.index < state.targets.length
        ? state.revealUntil > 0
          ? 'MEMORIZE'
          : `WHERE WAS ${state.targets[state.index]}?`
        : 'COMPLETE'
    case 'rule-switch':
      return promptFor(state.sub)
  }
}

export function createObjectiveState(
  type: ObjectiveType,
  cells: GridCell[],
  rng: SeededRng,
  opts: {
    divisor?: number
    targetCount?: number
    rulePhases?: { objective: ObjectiveType; durationSeconds: number }[]
  } = {},
): { state: ObjectiveState; prompt: string } {
  const values = cells.map((c) => c.value)
  let state: ObjectiveState

  switch (type) {
    case 'ascending':
      state = { type: 'ascending', queue: [...values].sort((a, b) => a - b) }
      break
    case 'descending':
      state = { type: 'descending', queue: [...values].sort((a, b) => b - a) }
      break
    case 'min-max':
      state = { type: 'min-max', mode: rng.next() < 0.5 ? 'min' : 'max', remaining: [...values] }
      break
    case 'odd-even': {
      const parity = rng.next() < 0.5 ? 'even' : 'odd'
      const queue = values
        .filter((v) => (parity === 'even' ? v % 2 === 0 : v % 2 !== 0))
        .sort((a, b) => a - b)
      state = { type: 'odd-even', parity, queue }
      break
    }
    case 'divisibility': {
      const divisor = opts.divisor ?? [3, 4, 5, 7][rng.nextInt(0, 3)]
      const remaining = values.filter((v) => v % divisor === 0)
      state = { type: 'divisibility', divisor, remaining }
      break
    }
    case 'target-hunt': {
      const count = opts.targetCount ?? 8
      const targets = rng.shuffle(values).slice(0, count)
      state = { type: 'target-hunt', targets, index: 0 }
      break
    }
    case 'memory': {
      const count = opts.targetCount ?? 5
      const targets = rng.shuffle(values).slice(0, count)
      state = { type: 'memory', targets, index: 0, revealUntil: MEMORY_REVEAL_MS, revealMs: MEMORY_REVEAL_MS }
      break
    }
    case 'rule-switch': {
      const phases = opts.rulePhases ?? []
      let cursor = 0
      const withTiming = phases.map((p) => {
        const startAt = cursor
        cursor += p.durationSeconds * 1000
        return { objective: p.objective, startAt, endAt: cursor }
      })
      const first = withTiming[0]
      const sub: ObjectiveState = first
        ? createObjectiveState(first.objective, cells, rng, opts).state
        : { type: 'ascending', queue: [] }
      state = { type: 'rule-switch', phases: withTiming, activePhaseIndex: 0, sub }
      break
    }
  }

  return { state, prompt: promptFor(state) }
}

/** Advances a rule-switch objective when its phase window has elapsed. */
export function tickObjective(
  state: ObjectiveState,
  elapsedMs: number,
  cells: GridCell[],
  rng: SeededRng,
): { state: ObjectiveState; prompt: string } {
  if (state.type !== 'rule-switch') return { state, prompt: promptFor(state) }

  const nextIndex = state.phases.findIndex((p) => elapsedMs >= p.startAt && elapsedMs < p.endAt)
  if (nextIndex === -1 || nextIndex === state.activePhaseIndex) {
    return { state, prompt: promptFor(state) }
  }
  const phase = state.phases[nextIndex]
  const sub = createObjectiveState(phase.objective, cells, rng).state
  const next: ObjectiveState = { ...state, activePhaseIndex: nextIndex, sub }
  return { state: next, prompt: promptFor(next) }
}

/** Applies elapsed time to a memory objective's reveal window. */
export function tickMemoryReveal(state: ObjectiveState, deltaMs: number): ObjectiveState {
  const target = state.type === 'rule-switch' ? state.sub : state
  if (target.type !== 'memory' || target.revealUntil <= 0) return state
  const revealUntil = Math.max(0, target.revealUntil - deltaMs)
  const nextMemory = { ...target, revealUntil }
  if (state.type === 'rule-switch') return { ...state, sub: nextMemory }
  return nextMemory
}

export function isRevealPhase(state: ObjectiveState): boolean {
  const target = state.type === 'rule-switch' ? state.sub : state
  return target.type === 'memory' && target.revealUntil > 0
}

/**
 * Validates a selected cell against the active objective. Returns the next
 * objective state (immutable) plus whether the pick was correct and whether
 * the whole objective is now complete.
 */
export function validateSelection(state: ObjectiveState, cell: GridCell): ObjectiveResult & { state: ObjectiveState } {
  if (state.type === 'rule-switch') {
    const inner = validateSelection(state.sub, cell)
    return { ...inner, state: { ...state, sub: inner.state } }
  }

  switch (state.type) {
    case 'ascending':
    case 'descending': {
      const [expected, ...rest] = state.queue
      const correct = expected === cell.value
      const nextQueue = correct ? rest : state.queue
      const next: ObjectiveState = { ...state, queue: nextQueue }
      return { correct, completed: correct && rest.length === 0, prompt: promptFor(next), state: next }
    }
    case 'min-max': {
      const extreme = state.mode === 'min' ? Math.min(...state.remaining) : Math.max(...state.remaining)
      const correct = cell.value === extreme
      const remaining = correct ? state.remaining.filter((v) => v !== cell.value) : state.remaining
      const next: ObjectiveState = { ...state, remaining }
      return { correct, completed: correct && remaining.length === 0, prompt: promptFor(next), state: next }
    }
    case 'odd-even': {
      const [expected, ...rest] = state.queue
      const correct = expected === cell.value
      const next: ObjectiveState = { ...state, queue: correct ? rest : state.queue }
      return { correct, completed: correct && rest.length === 0, prompt: promptFor(next), state: next }
    }
    case 'divisibility': {
      const correct = cell.value % state.divisor === 0 && state.remaining.includes(cell.value)
      const remaining = correct ? state.remaining.filter((v) => v !== cell.value) : state.remaining
      const next: ObjectiveState = { ...state, remaining }
      return { correct, completed: correct && remaining.length === 0, prompt: promptFor(next), state: next }
    }
    case 'target-hunt': {
      const expected = state.targets[state.index]
      const correct = cell.value === expected
      const index = correct ? state.index + 1 : state.index
      const next: ObjectiveState = { ...state, index }
      return { correct, completed: correct && index === state.targets.length, prompt: promptFor(next), state: next }
    }
    case 'memory': {
      if (state.revealUntil > 0) {
        return { correct: false, completed: false, prompt: promptFor(state), state }
      }
      const expected = state.targets[state.index]
      const correct = cell.value === expected
      const index = correct ? state.index + 1 : state.index
      const next: ObjectiveState = { ...state, index }
      return { correct, completed: correct && index === state.targets.length, prompt: promptFor(next), state: next }
    }
  }
}
