import type { GameConfig, GridCell } from '../types'
import { SeededRng } from './rng'

/**
 * Fills the grid with a shuffled, unique set of values drawn from
 * numberRange. When the range is wider than gridSize² (used by the
 * `distraction` mutator to raise digit collisions for target-hunt), a
 * random subset is chosen instead of the full range.
 */
export function generateGrid(config: GameConfig, rng: SeededRng): GridCell[] {
  const { gridSize, numberRange } = config
  const [min, max] = numberRange
  const cellCount = gridSize * gridSize
  const pool: number[] = []
  for (let v = min; v <= max; v++) pool.push(v)

  const values =
    pool.length === cellCount ? rng.shuffle(pool) : rng.shuffle(pool).slice(0, cellCount)

  const cells: GridCell[] = []
  for (let row = 0; row < gridSize; row++) {
    for (let col = 0; col < gridSize; col++) {
      const index = row * gridSize + col
      cells.push({ id: `${row}-${col}`, row, col, value: values[index] })
    }
  }
  return cells
}

/** Repositions existing values onto new cells (used by the `shuffle` mutator). */
export function reshuffleGrid(cells: GridCell[], rng: SeededRng): GridCell[] {
  const values = rng.shuffle(cells.map((c) => c.value))
  return cells.map((cell, i) => ({ ...cell, value: values[i] }))
}
