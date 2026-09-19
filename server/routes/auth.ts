import { Router } from 'express'
import bcrypt from 'bcryptjs'
import { db } from '../db'
import { newId } from '../lib/ids'
import { createGuestUser, createSessionForUser, requireAuth } from '../lib/auth'
import { getWalletBalance } from '../lib/coins'

export const authRouter = Router()

authRouter.post('/guest', (_req, res) => {
  const { user, token } = createGuestUser()
  res.json({ token, user: { ...user, coins: getWalletBalance(user.id) } })
})

authRouter.post('/register', (req, res) => {
  const { username, password } = req.body as { username?: string; password?: string }
  if (!username || !password || username.length < 3 || password.length < 6) {
    return res.status(400).json({ error: 'Username must be 3+ chars, password 6+ chars' })
  }

  const existing = db.prepare('SELECT id FROM users WHERE username = ?').get(username)
  if (existing) return res.status(409).json({ error: 'Username already taken' })

  // Upgrading an existing guest session keeps their coins, PBs, and history.
  const authHeader = req.headers.authorization
  const guestToken = authHeader?.startsWith('Bearer ') ? authHeader.slice(7) : null
  const guestSession = guestToken
    ? (db
        .prepare(`SELECT u.id, u.is_guest as isGuest FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?`)
        .get(guestToken) as { id: string; isGuest: number } | undefined)
    : undefined

  const passwordHash = bcrypt.hashSync(password, 10)

  if (guestSession?.isGuest) {
    db.prepare('UPDATE users SET username = ?, password_hash = ?, is_guest = 0, display_name = ? WHERE id = ?').run(
      username,
      passwordHash,
      username,
      guestSession.id,
    )
    const token = createSessionForUser(guestSession.id)
    return res.json({
      token,
      user: { id: guestSession.id, username, isGuest: false, displayName: username, coins: getWalletBalance(guestSession.id) },
    })
  }

  const id = newId('user')
  db.prepare('INSERT INTO users (id, username, password_hash, is_guest, display_name, created_at) VALUES (?, ?, ?, 0, ?, ?)').run(
    id,
    username,
    passwordHash,
    username,
    Date.now(),
  )
  const token = createSessionForUser(id)
  res.json({ token, user: { id, username, isGuest: false, displayName: username, coins: getWalletBalance(id) } })
})

authRouter.post('/login', (req, res) => {
  const { username, password } = req.body as { username?: string; password?: string }
  if (!username || !password) return res.status(400).json({ error: 'Missing credentials' })

  const row = db.prepare('SELECT id, password_hash as passwordHash, display_name as displayName FROM users WHERE username = ?').get(
    username,
  ) as { id: string; passwordHash: string | null; displayName: string } | undefined

  if (!row || !row.passwordHash || !bcrypt.compareSync(password, row.passwordHash)) {
    return res.status(401).json({ error: 'Invalid username or password' })
  }

  const token = createSessionForUser(row.id)
  res.json({ token, user: { id: row.id, username, isGuest: false, displayName: row.displayName, coins: getWalletBalance(row.id) } })
})

authRouter.get('/me', requireAuth, (req, res) => {
  res.json({ user: { ...req.user, coins: getWalletBalance(req.user!.id) } })
})
