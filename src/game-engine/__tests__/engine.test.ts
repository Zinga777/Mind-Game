import { describe, expect, it } from 'vitest'
import { buildGameConfig } from '../core/config'
import { createSession, selectCell, tick, remainingTimeMs } from '../core/session'
import { SeededRng } from '../core/rng'
import { computeScore } from '../scoring'
import { validateMutatorCombo } from '../mutators'
import { DIFFICULTY_PRESETS, clampMutatorsToDifficulty } from '../difficulty'

describe('SeededRng', () => {
  it('produces identical sequences for the same seed', () => {
    const a = new SeededRng('seed-123')
    const b = new SeededRng('seed-123')
    const seqA = Array.from({ length: 20 }, () => a.next())
    const seqB = Array.from({ length: 20 }, () => b.next())
    expect(seqA).toEqual(seqB)
  })

  it('produces different sequences for different seeds', () => {
    const a = new SeededRng('seed-A')
    const b = new SeededRng('seed-B')
    expect(a.next()).not.toBeCloseTo(b.next(), 5)
  })
})

describe('grid generation & session reproducibility', () => {
  it('same seed + config produces identical grid layout and objective', () => {
    const config = buildGameConfig({ objective: 'target-hunt', difficulty: 'advanced', seed: 'tournament-round-1' })
    const s1 = createSession(config, 0)
    const s2 = createSession(config, 0)
    expect(s1.cells.map((c) => c.value)).toEqual(s2.cells.map((c) => c.value))
    expect(s1.prompt).toEqual(s2.prompt)
  })

  it('fills a 10x10 grid with 100 unique values by default', () => {
    const config = buildGameConfig({ objective: 'ascending', difficulty: 'beginner', seed: 'x' })
    const session = createSession(config, 0)
    expect(session.cells).toHaveLength(100)
    expect(new Set(session.cells.map((c) => c.value)).size).toBe(100)
  })
})

describe('ascending objective', () => {
  it('only accepts the next value in order and completes after all 100', () => {
    const config = buildGameConfig({ objective: 'ascending', difficulty: 'beginner', seed: 'ascend-1' })
    let session = createSession(config, 0)

    const sorted = [...session.cells].sort((a, b) => a.value - b.value)
    // Wrong pick (second-lowest instead of lowest) should not advance the queue.
    session = selectCell(session, sorted[1].id, 1000)
    expect(session.incorrectCount).toBe(1)
    expect(session.correctCount).toBe(0)

    for (const cell of sorted) {
      session = selectCell(session, cell.id, session.lastEventAtMs + 500)
    }
    expect(session.status).toBe('completed')
    expect(session.correctCount).toBe(100)
  })
})

describe('target-hunt objective', () => {
  it('requires targets to be found in the generated order', () => {
    const config = buildGameConfig({ objective: 'target-hunt', difficulty: 'advanced', seed: 'hunt-1' })
    let session = createSession(config, 0)
    expect(session.objective.type).toBe('target-hunt')
    if (session.objective.type !== 'target-hunt') throw new Error('unreachable')

    const firstTarget = session.objective.targets[0]
    const cell = session.cells.find((c) => c.value === firstTarget)!
    session = selectCell(session, cell.id, 500)
    expect(session.correctCount).toBe(1)
    expect(session.objective.type === 'target-hunt' && session.objective.index).toBe(1)
  })
})

describe('mutator validation', () => {
  it('rejects incompatible shuffle + vanish combo', () => {
    expect(validateMutatorCombo(['shuffle', 'vanish']).valid).toBe(false)
  })

  it('accepts compatible combos', () => {
    expect(validateMutatorCombo(['shuffle', 'precision']).valid).toBe(true)
  })

  it('clamps mutators to what the difficulty preset allows', () => {
    const clamped = clampMutatorsToDifficulty(['shuffle', 'precision', 'turbo'], 'beginner')
    expect(clamped).toEqual([])
  })
})

describe('difficulty presets', () => {
  it('increases score multiplier and penalty as difficulty rises', () => {
    const levels = ['beginner', 'intermediate', 'advanced', 'expert', 'master'] as const
    for (let i = 1; i < levels.length; i++) {
      expect(DIFFICULTY_PRESETS[levels[i]].scoreMultiplier).toBeGreaterThan(DIFFICULTY_PRESETS[levels[i - 1]].scoreMultiplier)
      expect(DIFFICULTY_PRESETS[levels[i]].wrongTapPenalty).toBeGreaterThan(DIFFICULTY_PRESETS[levels[i - 1]].wrongTapPenalty)
    }
  })
})

describe('scoring engine', () => {
  const config = buildGameConfig({ objective: 'ascending', difficulty: 'advanced', seed: 'score-1' })

  it('every field sums to the final score', () => {
    const events = [
      { cellId: 'a', value: 1, correct: true, timestampMs: 100, reactionMs: 400 },
      { cellId: 'b', value: 2, correct: true, timestampMs: 600, reactionMs: 500 },
      { cellId: 'c', value: 3, correct: false, timestampMs: 900, reactionMs: 300 },
    ]
    const result = computeScore(events, config, 20000, 2)
    const sum = result.baseScore + result.speedBonus + result.comboBonus + result.timeBonus - result.penalties
    expect(result.finalScore).toBe(Math.max(0, sum))
  })

  it('never goes negative even with many mistakes', () => {
    const events = Array.from({ length: 20 }, (_, i) => ({
      cellId: `c${i}`,
      value: i,
      correct: false,
      timestampMs: i * 100,
      reactionMs: 1000,
    }))
    const result = computeScore(events, config, 0, 0)
    expect(result.finalScore).toBe(0)
  })

  it('computes accuracy from correct/total attempts', () => {
    const events = [
      { cellId: 'a', value: 1, correct: true, timestampMs: 0, reactionMs: 100 },
      { cellId: 'b', value: 2, correct: false, timestampMs: 0, reactionMs: 100 },
    ]
    const result = computeScore(events, config, 0, 1)
    expect(result.accuracy).toBe(0.5)
  })
})

describe('timer', () => {
  it('counts down and completes the session when time expires', () => {
    const config = buildGameConfig({ objective: 'ascending', difficulty: 'beginner', seed: 'timer-1', durationSeconds: 5 })
    let session = createSession(config, 0)
    expect(remainingTimeMs(session, 2000)).toBe(3000)

    session = tick(session, 6000, 6000)
    expect(session.status).toBe('completed')
  })
})

describe('shuffle mutator', () => {
  it('reshuffles cell values at the configured interval, deterministically per seed', () => {
    const config = buildGameConfig({
      objective: 'ascending',
      difficulty: 'advanced',
      mutators: ['shuffle'],
      seed: 'shuffle-1',
    })
    let session = createSession(config, 0)
    const before = session.cells.map((c) => c.value)
    session = tick(session, 9000, 9000)
    const after = session.cells.map((c) => c.value)
    expect(after).not.toEqual(before)
    expect(new Set(after).size).toBe(new Set(before).size)
  })
})

describe('memory objective', () => {
  it('blocks selection during the reveal window, then accepts recall', () => {
    const config = buildGameConfig({ objective: 'memory', difficulty: 'advanced', seed: 'memory-1' })
    let session = createSession(config, 0)
    if (session.objective.type !== 'memory') throw new Error('unreachable')
    const target = session.objective.targets[0]
    const cell = session.cells.find((c) => c.value === target)!

    // Still revealing: selection should be ignored.
    session = selectCell(session, cell.id, 100)
    expect(session.correctCount).toBe(0)
    expect(session.incorrectCount).toBe(0)

    session = tick(session, 3000, 3000)
    session = selectCell(session, cell.id, 3100)
    expect(session.correctCount).toBe(1)
  })
})
