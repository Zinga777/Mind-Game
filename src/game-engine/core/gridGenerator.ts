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

/**
 * Rotates the values 90° clockwise within the fixed cell layout (used by the
 * `rotation` mutator). Cell identities/positions never move — only which
 * value sits where — so selection targets stay valid mid-rotation.
 */
export function rotateGridValues(cells: GridCell[], gridSize: number): GridCell[] {
  const grid: number[][] = Array.from({ length: gridSize }, () => Array(gridSize).fill(0))
  for (const cell of cells) grid[cell.row][cell.col] = cell.value

  const rotated: number[][] = Array.from({ length: gridSize }, () => Array(gridSize).fill(0))
  for (let r = 0; r < gridSize; r++) {
    for (let c = 0; c < gridSize; c++) {
      rotated[c][gridSize - 1 - r] = grid[r][c]
    }
  }
  return cells.map((cell) => ({ ...cell, value: rotated[cell.row][cell.col] }))
}

/** Mirrors the grid's values horizontally (used by the `mirror` mutator). */
export function mirrorGridValues(cells: GridCell[], gridSize: number): GridCell[] {
  const grid: number[][] = Array.from({ length: gridSize }, () => Array(gridSize).fill(0))
  for (const cell of cells) grid[cell.row][cell.col] = cell.value
  return cells.map((cell) => ({ ...cell, value: grid[cell.row][gridSize - 1 - cell.col] }))
}

/** Swaps the values of two specific cells (used by the `moving-targets` mutator). */
export function swapCellValues(cells: GridCell[], cellIdA: string, cellIdB: string): GridCell[] {
  const a = cells.find((c) => c.id === cellIdA)
  const b = cells.find((c) => c.id === cellIdB)
  if (!a || !b) return cells
  return cells.map((cell) => {
    if (cell.id === cellIdA) return { ...cell, value: b.value }
    if (cell.id === cellIdB) return { ...cell, value: a.value }
    return cell
  })
}
