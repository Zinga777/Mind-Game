import type { NextFunction, Request, Response } from 'express'
import { randomUUID } from 'node:crypto'
import { db } from '../db'
import { newId } from './ids'
import { applyCoinTransaction } from './coins'

const SESSION_TTL_MS = 90 * 24 * 60 * 60 * 1000 // 90 days

export interface AuthedUser {
  id: string
  username: string | null
  isGuest: boolean
  displayName: string
}

export function createSessionForUser(userId: string): string {
  const token = randomUUID()
  const now = Date.now()
  db.prepare('INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)').run(
    token,
    userId,
    now,
    now + SESSION_TTL_MS,
  )
  return token
}

export function createGuestUser(): { user: AuthedUser; token: string } {
  const id = newId('user')
  const displayName = `Athlete${Math.floor(1000 + Math.random() * 9000)}`
  db.prepare('INSERT INTO users (id, username, password_hash, is_guest, display_name, created_at) VALUES (?, NULL, NULL, 1, ?, ?)').run(
    id,
    displayName,
    Date.now(),
  )
  // Welcome bonus — a real, server-issued grant, not a client-side number.
  applyCoinTransaction(id, 'EARNED', 50, 'welcome_bonus')
  const token = createSessionForUser(id)
  return { user: { id, username: null, isGuest: true, displayName }, token }
}

export function requireAuth(req: Request, res: Response, next: NextFunction) {
  const header = req.headers.authorization
  const token = header?.startsWith('Bearer ') ? header.slice(7) : null
  if (!token) return res.status(401).json({ error: 'Missing bearer token' })

  const row = db
    .prepare(
      `SELECT u.id, u.username, u.is_guest as isGuest, u.display_name as displayName, s.expires_at as expiresAt
       FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?`,
    )
    .get(token) as { id: string; username: string | null; isGuest: number; displayName: string; expiresAt: number } | undefined

  if (!row || row.expiresAt < Date.now()) {
    return res.status(401).json({ error: 'Invalid or expired session' })
  }

  req.user = { id: row.id, username: row.username, isGuest: Boolean(row.isGuest), displayName: row.displayName }
  next()
}

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      user?: AuthedUser
    }
  }
}
