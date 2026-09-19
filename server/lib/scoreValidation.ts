import { generateGrid, SeededRng, computeScore, type GameConfig, type SelectionEvent, type ScoreBreakdown } from '../../src/game-engine'

export interface SubmittedAttempt {
  config: GameConfig
  events: SelectionEvent[]
  remainingTimeMs: number
  bestCombo: number
}

export interface ValidationResult {
  valid: boolean
  reason?: string
  score?: ScoreBreakdown
}

/**
 * Recomputes the score server-side from the raw event log instead of
 * trusting a client-submitted total, and checks every selected cell actually
 * existed in the grid the seed would have produced. This is deliberately not
 * full cheat-proof replay validation (that needs server-tracked timing —
 * see README roadmap, "anti-cheat"); it closes the two cheap attacks
 * (fabricated score, fabricated cell values) that are trivial without it.
 */
export function validateAttempt(attempt: SubmittedAttempt): ValidationResult {
  const { config, events, remainingTimeMs, bestCombo } = attempt

  if (config.gridSize <= 0 || config.gridSize > 20) return { valid: false, reason: 'Invalid grid size' }
  const maxCells = config.gridSize * config.gridSize
  if (events.length > maxCells) return { valid: false, reason: 'Too many selection events for this grid' }
  if (remainingTimeMs < 0 || remainingTimeMs > config.durationSeconds * 1000) {
    return { valid: false, reason: 'Invalid remaining time' }
  }
  if (bestCombo < 0 || bestCombo > maxCells) return { valid: false, reason: 'Invalid combo value' }

  const rng = new SeededRng(config.seed)
  const cells = generateGrid(config, rng)
  const validValuesByCell = new Map(cells.map((c) => [c.id, c.value]))

  for (const event of events) {
    const expectedValue = validValuesByCell.get(event.cellId)
    if (expectedValue === undefined) return { valid: false, reason: `Unknown cell ${event.cellId}` }
    if (expectedValue !== event.value) return { valid: false, reason: `Cell ${event.cellId} value mismatch` }
    if (event.reactionMs < 0 || event.reactionMs > config.durationSeconds * 1000) {
      return { valid: false, reason: 'Implausible reaction time' }
    }
  }

  const score = computeScore(events, config, remainingTimeMs, bestCombo)
  return { valid: true, score }
}
