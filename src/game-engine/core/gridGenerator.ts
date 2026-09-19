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

/** Numbers with any two adjacent digits swapped, e.g. 68 → 86, 168 → 618/186. */
function digitSwapVariants(n: number): number[] {
  const s = String(n)
  const variants = new Set<number>()
  for (let i = 0; i < s.length - 1; i++) {
    const arr = s.split('')
    ;[arr[i], arr[i + 1]] = [arr[i + 1], arr[i]]
    if (arr[0] !== '0') variants.add(Number(arr.join('')))
  }
  variants.delete(n)
  return [...variants]
}

/** Numbers one digit-position off by a small amount, e.g. 68 → 69, 67, 66, 88, 58, 78. */
function digitNudgeVariants(n: number): number[] {
  const s = String(n)
  const variants = new Set<number>()
  for (let i = 0; i < s.length; i++) {
    for (const delta of [-2, -1, 1, 2]) {
      const d = Number(s[i]) + delta
      if (d < 0 || d > 9) continue
      if (i === 0 && d === 0 && s.length > 1) continue
      const arr = s.split('')
      arr[i] = String(d)
      variants.add(Number(arr.join('')))
    }
  }
  variants.delete(n)
  return [...variants]
}

/**
 * Numbers visually confusable with `n` — a digit swap or a small per-digit
 * nudge — used to deliberately seed a grid with genuine "I saw it but
 * tapped wrong" near-misses (68/86/69/66/88) instead of making a challenge
 * harder through unreadable text or arbitrary density.
 */
export function confusableCandidates(n: number): number[] {
  return [...new Set([...digitSwapVariants(n), ...digitNudgeVariants(n)])]
}

/**
 * Builds a grid whose target-hunt targets are chosen first, each seeded
 * with 1-2 digit-confusable distractors nearby in the value pool, with the
 * remaining cells filled from the rest of the range. Used when the
 * `distraction` mutator is active on Target Hunt — this is what makes
 * distractors *meaningfully* similar (68 next to 86, 69, 66, 88) rather
 * than just statistically more likely from a wider random range.
 */
export function generateConfusableGrid(
  config: GameConfig,
  rng: SeededRng,
  targetCount: number,
): { cells: GridCell[]; targets: number[] } {
  const { gridSize, numberRange } = config
  const [min, max] = numberRange
  const cellCount = gridSize * gridSize

  const used = new Set<number>()
  const targets: number[] = []
  let guard = 0
  while (targets.length < targetCount && guard < 10000) {
    guard++
    const candidate = rng.nextInt(min, max)
    if (used.has(candidate)) continue
    used.add(candidate)
    targets.push(candidate)
  }

  const values: number[] = [...targets]
  for (const t of targets) {
    const candidates = rng.shuffle(confusableCandidates(t)).filter((c) => c >= min && c <= max && !used.has(c))
    for (const c of candidates.slice(0, 2)) {
      used.add(c)
      values.push(c)
    }
  }

  guard = 0
  while (values.length < cellCount && guard < 20000) {
    guard++
    const candidate = rng.nextInt(min, max)
    if (used.has(candidate)) continue
    used.add(candidate)
    values.push(candidate)
  }

  const shuffledValues = rng.shuffle(values.slice(0, cellCount))
  const cells: GridCell[] = []
  for (let row = 0; row < gridSize; row++) {
    for (let col = 0; col < gridSize; col++) {
      const index = row * gridSize + col
      cells.push({ id: `${row}-${col}`, row, col, value: shuffledValues[index] })
    }
  }
  return { cells, targets: rng.shuffle(targets) }
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
