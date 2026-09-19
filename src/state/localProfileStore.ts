import type { DifficultyLevel, ObjectiveType, ScoreBreakdown } from '../game-engine/types'

/**
 * Guest-mode persistence. This is intentionally a thin, swappable adapter:
 * the interface below (`ProfileStore`) is what a real backend-backed
 * implementation would satisfy once accounts/DB exist (see README "Data
 * ownership"). Nothing here is presented as server-authoritative — it's
 * local-only progress for players who haven't created an account, and it
 * never fabricates leaderboard rank, coins, or other data that must come
 * from a server.
 */

export interface RunRecord {
  id: string
  objective: ObjectiveType
  difficulty: DifficultyLevel
  mutators: string[]
  score: ScoreBreakdown
  playedAtMs: number
}

export interface ProfileSnapshot {
  runs: RunRecord[]
  personalBests: Partial<Record<ObjectiveType, number>>
  streak: { current: number; longest: number; lastPlayedDateKey: string | null }
}

const STORAGE_KEY = 'mind-athlete:guest-profile:v1'

function emptySnapshot(): ProfileSnapshot {
  return { runs: [], personalBests: {}, streak: { current: 0, longest: 0, lastPlayedDateKey: null } }
}

function dateKey(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

function load(): ProfileSnapshot {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return emptySnapshot()
    const parsed = JSON.parse(raw) as ProfileSnapshot
    return { ...emptySnapshot(), ...parsed }
  } catch {
    return emptySnapshot()
  }
}

function save(snapshot: ProfileSnapshot): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
  } catch {
    // Storage unavailable (private mode, quota) — progress simply won't persist this session.
  }
}

function updateStreak(snapshot: ProfileSnapshot, playedAtMs: number): ProfileSnapshot['streak'] {
  const today = dateKey(playedAtMs)
  const { lastPlayedDateKey, current, longest } = snapshot.streak
  if (lastPlayedDateKey === today) return snapshot.streak

  const yesterday = dateKey(playedAtMs - 24 * 60 * 60 * 1000)
  const isConsecutive = lastPlayedDateKey === yesterday
  const nextCurrent = isConsecutive ? current + 1 : 1
  return { current: nextCurrent, longest: Math.max(longest, nextCurrent), lastPlayedDateKey: today }
}

export interface RecordRunResult {
  snapshot: ProfileSnapshot
  isNewPersonalBest: boolean
  previousBest: number | null
}

export function recordRun(run: Omit<RunRecord, 'id'>): RecordRunResult {
  const snapshot = load()
  const id = `${run.playedAtMs}-${Math.random().toString(36).slice(2, 8)}`
  const previousBest = snapshot.personalBests[run.objective] ?? null
  const isNewPersonalBest = previousBest === null || run.score.finalScore > previousBest

  const next: ProfileSnapshot = {
    runs: [{ ...run, id }, ...snapshot.runs].slice(0, 200),
    personalBests: {
      ...snapshot.personalBests,
      [run.objective]: isNewPersonalBest ? run.score.finalScore : previousBest,
    },
    streak: updateStreak(snapshot, run.playedAtMs),
  }
  save(next)
  return { snapshot: next, isNewPersonalBest, previousBest }
}

export function getProfile(): ProfileSnapshot {
  return load()
}

export function clearProfile(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}
