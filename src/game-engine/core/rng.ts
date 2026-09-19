/**
 * Deterministic PRNG (mulberry32) seeded from a string. Every draw an engine
 * makes — grid layout, target order, shuffle timing — must come from this so
 * a given seed always reproduces the same challenge.
 */

function hashStringToSeed(seed: string): number {
  let h = 1779033703 ^ seed.length
  for (let i = 0; i < seed.length; i++) {
    h = Math.imul(h ^ seed.charCodeAt(i), 3432918353)
    h = (h << 13) | (h >>> 19)
  }
  return h >>> 0
}

export class SeededRng {
  private state: number

  constructor(seed: string) {
    this.state = hashStringToSeed(seed) || 1
  }

  /** Returns a float in [0, 1). */
  next(): number {
    this.state |= 0
    this.state = (this.state + 0x6d2b79f5) | 0
    let t = Math.imul(this.state ^ (this.state >>> 15), 1 | this.state)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }

  /** Integer in [min, max]. */
  nextInt(min: number, max: number): number {
    return Math.floor(this.next() * (max - min + 1)) + min
  }

  shuffle<T>(items: T[]): T[] {
    const arr = items.slice()
    for (let i = arr.length - 1; i > 0; i--) {
      const j = this.nextInt(0, i)
      ;[arr[i], arr[j]] = [arr[j], arr[i]]
    }
    return arr
  }
}
