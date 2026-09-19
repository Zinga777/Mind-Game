import { apiFetch } from '../lib/api'
import type { GameConfig, SelectionEvent } from '../game-engine/types'

/**
 * Score submissions are queued here when the API call fails (offline,
 * server restarting, etc.) instead of being silently dropped — per the
 * product rule "never silently lose a score." The queue is flushed
 * automatically on the next successful app load / network recovery.
 */

export interface PendingAttempt {
  id: string
  config: GameConfig
  events: SelectionEvent[]
  remainingTimeMs: number
  bestCombo: number
  queuedAtMs: number
}

const QUEUE_KEY = 'mind-athlete:pending-attempts:v1'

function load(): PendingAttempt[] {
  try {
    const raw = localStorage.getItem(QUEUE_KEY)
    return raw ? (JSON.parse(raw) as PendingAttempt[]) : []
  } catch {
    return []
  }
}

function save(queue: PendingAttempt[]): void {
  try {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue))
  } catch {
    // ignore
  }
}

export function enqueuePendingAttempt(attempt: Omit<PendingAttempt, 'id' | 'queuedAtMs'>): void {
  const queue = load()
  queue.push({ ...attempt, id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, queuedAtMs: Date.now() })
  save(queue)
}

export function pendingAttemptCount(): number {
  return load().length
}

export async function flushPendingAttempts(): Promise<{ flushed: number; stillPending: number }> {
  const queue = load()
  if (queue.length === 0) return { flushed: 0, stillPending: 0 }

  const remaining: PendingAttempt[] = []
  let flushed = 0
  for (const attempt of queue) {
    try {
      await apiFetch('/game-attempts', {
        method: 'POST',
        body: { config: attempt.config, events: attempt.events, remainingTimeMs: attempt.remainingTimeMs, bestCombo: attempt.bestCombo },
      })
      flushed++
    } catch {
      remaining.push(attempt)
    }
  }
  save(remaining)
  return { flushed, stillPending: remaining.length }
}
