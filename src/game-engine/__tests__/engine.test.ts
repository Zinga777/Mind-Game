import { describe, expect, it } from 'vitest'
import { buildGameConfig } from '../core/config'
import { createSession, selectCell, tick, remainingTimeMs, isBlind } from '../core/session'
import { SeededRng } from '../core/rng'
import { computeScore } from '../scoring'
import { validateMutatorCombo, resolveCompatibleMutators } from '../mutators'
import { DIFFICULTY_PRESETS, clampMutatorsToDifficulty } from '../difficulty'
import { computeThunderReward, costForDifficulty, DEFAULT_THUNDER_CONFIG } from '../thunder'
import { analyzeMindDna, generateInsights, type AttemptSample } from '../performance'
import { compareToGhost } from '../ghost'
import { evaluateAchievements, checkPbBreaker } from '../achievements'
import { computeProgressionScore, levelForScore } from '../progression'
import type { ScoreBreakdown } from '../types'

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

describe('resolveCompatibleMutators', () => {
  it('drops a later mutator that conflicts with an earlier one', () => {
    expect(resolveCompatibleMutators(['shuffle', 'rotation', 'precision'])).toEqual(['shuffle', 'precision'])
    expect(resolveCompatibleMutators(['rotation', 'mirror'])).toEqual(['rotation'])
  })

  it('keeps compatible combinations intact', () => {
    expect(resolveCompatibleMutators(['precision', 'turbo', 'distraction'])).toEqual(['precision', 'turbo', 'distraction'])
  })
})

describe('rotation mutator', () => {
  it('rotates cell values on schedule without changing the set of values present', () => {
    const config = buildGameConfig({ objective: 'ascending', difficulty: 'expert', mutators: ['rotation'], seed: 'rotate-1' })
    let session = createSession(config, 0)
    const before = session.cells.map((c) => c.value)
    session = tick(session, 20000, 20000)
    const after = session.cells.map((c) => c.value)
    expect(after).not.toEqual(before)
    expect([...after].sort()).toEqual([...before].sort())
    expect(session.rotationSeq).toBeGreaterThan(0)
  })
})

describe('mirror mutator', () => {
  it('mirrors row values horizontally', () => {
    const config = buildGameConfig({ objective: 'ascending', difficulty: 'expert', mutators: ['mirror'], seed: 'mirror-1' })
    let session = createSession(config, 0)
    const beforeRow0 = session.cells.filter((c) => c.row === 0).sort((a, b) => a.col - b.col).map((c) => c.value)
    session = tick(session, 20000, 20000)
    const afterRow0 = session.cells.filter((c) => c.row === 0).sort((a, b) => a.col - b.col).map((c) => c.value)
    expect(afterRow0).toEqual([...beforeRow0].reverse())
  })
})

describe('moving-targets mutator', () => {
  it('relocates the active target value without changing the value set', () => {
    const config = buildGameConfig({
      objective: 'target-hunt',
      difficulty: 'expert',
      mutators: ['moving-targets'],
      seed: 'moving-1',
    })
    let session = createSession(config, 0)
    const before = session.cells.map((c) => c.value).sort((a, b) => a - b)
    session = tick(session, 10000, 10000)
    const after = session.cells.map((c) => c.value).sort((a, b) => a - b)
    expect(after).toEqual(before)
    expect(session.movingTargetSeq).toBeGreaterThan(0)
  })
})

describe('locked-cells mutator', () => {
  it('locks a batch of cells that reject selection, then unlocks them', () => {
    const config = buildGameConfig({
      objective: 'ascending',
      difficulty: 'expert',
      mutators: ['locked-cells'],
      seed: 'locked-1',
    })
    let session = createSession(config, 0)
    session = tick(session, 6000, 6000)
    expect(session.lockedCellIds.length).toBeGreaterThan(0)

    const lockedId = session.lockedCellIds[0]
    const before = session.correctCount + session.incorrectCount
    session = selectCell(session, lockedId, 6100)
    expect(session.correctCount + session.incorrectCount).toBe(before) // selection ignored

    const stillLocked = session.lockedCellIds
    session = tick(session, 12000, 6000)
    expect(session.cellVisualState[stillLocked[0]]).not.toBe('locked')
  })
})

describe('blind-phase mutator', () => {
  it('blocks selection during the blind window and allows it after', () => {
    const config = buildGameConfig({
      objective: 'ascending',
      difficulty: 'expert',
      mutators: ['blind-phase'],
      seed: 'blind-1',
    })
    let session = createSession(config, 0)
    session = tick(session, 10000, 10000)
    expect(isBlind(session, 10000)).toBe(true)

    const anyCell = session.cells[0]
    session = selectCell(session, anyCell.id, 10100)
    expect(session.correctCount + session.incorrectCount).toBe(0)

    expect(isBlind(session, 12000)).toBe(false)
  })
})

describe('thunder economy', () => {
  it('scales cost with difficulty tier', () => {
    expect(costForDifficulty('beginner')).toBe(DEFAULT_THUNDER_CONFIG.standardGameCost)
    expect(costForDifficulty('advanced')).toBe(DEFAULT_THUNDER_CONFIG.hardGameCost)
    expect(costForDifficulty('master')).toBe(DEFAULT_THUNDER_CONFIG.expertGameCost)
  })

  const baseScore: ScoreBreakdown = {
    baseScore: 100,
    speedBonus: 0,
    comboBonus: 0,
    timeBonus: 0,
    penalties: 0,
    finalScore: 100,
    accuracy: 0.5,
    avgReactionMs: 500,
    correctCount: 5,
    incorrectCount: 5,
    bestCombo: 2,
  }

  it('always awards the completion reward, nothing else below thresholds', () => {
    const reward = computeThunderReward({ score: baseScore, isPersonalBest: false, newAchievementsCount: 0 })
    expect(reward.total).toBe(DEFAULT_THUNDER_CONFIG.completionReward)
  })

  it('adds accuracy, combo, PB, and achievement bonuses when earned', () => {
    const reward = computeThunderReward(
      { score: { ...baseScore, accuracy: 0.95, bestCombo: 10 }, isPersonalBest: true, newAchievementsCount: 2 },
      DEFAULT_THUNDER_CONFIG,
    )
    expect(reward.total).toBe(
      DEFAULT_THUNDER_CONFIG.completionReward +
        DEFAULT_THUNDER_CONFIG.accuracyBonus +
        DEFAULT_THUNDER_CONFIG.comboBonus +
        DEFAULT_THUNDER_CONFIG.pbBonus +
        DEFAULT_THUNDER_CONFIG.achievementBonus * 2,
    )
  })
})

describe('PerformanceAnalyzer / Mind DNA', () => {
  function sample(overrides: Partial<AttemptSample['score']> & { objective?: AttemptSample['objective']; mutators?: AttemptSample['mutators'] } = {}): AttemptSample {
    const { objective, mutators, ...scoreOverrides } = overrides
    return {
      objective: objective ?? 'ascending',
      difficulty: 'advanced',
      mutators: mutators ?? [],
      playedAt: Date.now(),
      score: {
        baseScore: 100,
        speedBonus: 0,
        comboBonus: 0,
        timeBonus: 0,
        penalties: 0,
        finalScore: 100,
        accuracy: 0.8,
        avgReactionMs: 600,
        correctCount: 8,
        incorrectCount: 2,
        bestCombo: 5,
        ...scoreOverrides,
      },
    }
  }

  it('returns default balanced metrics with no history', () => {
    const result = analyzeMindDna([])
    expect(result.sampleSize).toBe(0)
    expect(result.archetype).toBe('All-Rounder')
  })

  it('produces metrics in range 0-100 and identifies a strongest/weakest metric', () => {
    const result = analyzeMindDna([sample(), sample({ accuracy: 0.9 }), sample({ accuracy: 0.95 })])
    for (const value of Object.values(result.metrics)) {
      expect(value).toBeGreaterThanOrEqual(0)
      expect(value).toBeLessThanOrEqual(100)
    }
    expect(result.strongest).not.toBe(result.improvementArea)
  })

  it('is deterministic for the same input', () => {
    const samples = [sample({ accuracy: 0.7 }), sample({ accuracy: 0.85, avgReactionMs: 400 })]
    expect(analyzeMindDna(samples)).toEqual(analyzeMindDna(samples))
  })

  it('generates an insight comparing the latest run to the recent average', () => {
    const samples = [sample({ accuracy: 0.95, finalScore: 200 }), sample({ accuracy: 0.6 }), sample({ accuracy: 0.6 }), sample({ accuracy: 0.6 })]
    const insights = generateInsights(samples)
    expect(insights.length).toBeGreaterThan(0)
    expect(insights.some((i) => i.toLowerCase().includes('accuracy'))).toBe(true)
  })
})

describe('ghost comparison', () => {
  it('reports ahead when the live run has more correct picks than the ghost had by this time', () => {
    const ghostEvents = [
      { cellId: 'a', value: 1, correct: true, timestampMs: 500, reactionMs: 500 },
      { cellId: 'b', value: 2, correct: true, timestampMs: 1200, reactionMs: 700 },
    ]
    const result = compareToGhost(ghostEvents, 1000, 2)
    expect(result.ghostProgress).toBe(1)
    expect(result.status).toBe('ahead')
    expect(result.delta).toBe(1)
  })

  it('reports behind when trailing the ghost', () => {
    const ghostEvents = [
      { cellId: 'a', value: 1, correct: true, timestampMs: 200, reactionMs: 200 },
      { cellId: 'b', value: 2, correct: true, timestampMs: 400, reactionMs: 200 },
    ]
    const result = compareToGhost(ghostEvents, 1000, 1)
    expect(result.status).toBe('behind')
  })
})

describe('achievements', () => {
  function attempt(overrides: Partial<AttemptSample['score']> = {}, extra: Partial<Pick<AttemptSample, 'objective' | 'mutators'>> = {}): AttemptSample {
    return {
      objective: extra.objective ?? 'ascending',
      difficulty: 'advanced',
      mutators: extra.mutators ?? [],
      playedAt: Date.now(),
      score: {
        baseScore: 100,
        speedBonus: 0,
        comboBonus: 0,
        timeBonus: 0,
        penalties: 0,
        finalScore: 100,
        accuracy: 0.8,
        avgReactionMs: 600,
        correctCount: 8,
        incorrectCount: 2,
        bestCombo: 5,
        ...overrides,
      },
    }
  }

  it('always unlocks first-step on any completed run', () => {
    const latest = attempt()
    const unlocked = evaluateAchievements({ latest, history: [latest], progressionLevel: 'Rookie' })
    expect(unlocked).toContain('first-step')
  })

  it('unlocks no-mistakes only with zero incorrect and enough picks', () => {
    const clean = attempt({ incorrectCount: 0, correctCount: 6 })
    expect(evaluateAchievements({ latest: clean, history: [clean], progressionLevel: 'Rookie' })).toContain('no-mistakes')

    const dirty = attempt({ incorrectCount: 1, correctCount: 6 })
    expect(evaluateAchievements({ latest: dirty, history: [dirty], progressionLevel: 'Rookie' })).not.toContain('no-mistakes')
  })

  it('unlocks memory-builder only for high-accuracy memory runs', () => {
    const memRun = attempt({ accuracy: 0.95 }, { objective: 'memory' })
    expect(evaluateAchievements({ latest: memRun, history: [memRun], progressionLevel: 'Rookie' })).toContain('memory-builder')
  })

  it('unlocks grid-master only at Master progression level', () => {
    const run = attempt()
    expect(evaluateAchievements({ latest: run, history: [run], progressionLevel: 'Expert' })).not.toContain('grid-master')
    expect(evaluateAchievements({ latest: run, history: [run], progressionLevel: 'Master' })).toContain('grid-master')
  })

  it('checkPbBreaker requires at least 10 personal bests', () => {
    expect(checkPbBreaker(9)).toBe(false)
    expect(checkPbBreaker(10)).toBe(true)
  })
})

describe('progression', () => {
  it('rewards accuracy and PBs more than raw game count', () => {
    const grinder = computeProgressionScore({ totalGames: 200, personalBestCount: 0, averageAccuracy: 0.5 })
    const master = computeProgressionScore({ totalGames: 20, personalBestCount: 15, averageAccuracy: 0.95 })
    expect(master).toBeGreaterThan(grinder)
  })

  it('maps score to the correct level tier', () => {
    expect(levelForScore(0)).toBe('Rookie')
    expect(levelForScore(25)).toBe('Learner')
    expect(levelForScore(310)).toBe('Master')
  })
})
