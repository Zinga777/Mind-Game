import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { apiFetch, clearToken, getToken, setToken } from '../lib/api'
import { flushPendingAttempts } from './offlineQueue'

export interface SessionUser {
  id: string
  username: string | null
  isGuest: boolean
  displayName: string
  coins: number
}

interface SessionContextValue {
  user: SessionUser | null
  loading: boolean
  refresh: () => Promise<void>
  register: (username: string, password: string) => Promise<void>
  login: (username: string, password: string) => Promise<void>
  logoutToGuest: () => Promise<void>
}

const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null)
  const [loading, setLoading] = useState(true)

  const bootstrap = useCallback(async () => {
    setLoading(true)
    try {
      const existingToken = getToken()
      if (existingToken) {
        try {
          const { user: me } = await apiFetch<{ user: SessionUser }>('/auth/me')
          setUser(me)
          flushPendingAttempts()
          return
        } catch {
          clearToken()
        }
      }
      const { token, user: guest } = await apiFetch<{ token: string; user: SessionUser }>('/auth/guest', {
        method: 'POST',
        auth: false,
      })
      setToken(token)
      setUser(guest)
    } catch {
      // API unreachable — the app still renders; screens that need the
      // backend (leaderboard, results submission) surface their own error.
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    bootstrap()
  }, [bootstrap])

  const refresh = useCallback(async () => {
    try {
      const { user: me } = await apiFetch<{ user: SessionUser }>('/auth/me')
      setUser(me)
    } catch {
      // keep last known user
    }
  }, [])

  const register = useCallback(async (username: string, password: string) => {
    const { token, user: registered } = await apiFetch<{ token: string; user: SessionUser }>('/auth/register', {
      method: 'POST',
      body: { username, password },
    })
    setToken(token)
    setUser(registered)
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const { token, user: loggedIn } = await apiFetch<{ token: string; user: SessionUser }>('/auth/login', {
      method: 'POST',
      body: { username, password },
      auth: false,
    })
    setToken(token)
    setUser(loggedIn)
  }, [])

  const logoutToGuest = useCallback(async () => {
    clearToken()
    await bootstrap()
  }, [bootstrap])

  const value = useMemo(
    () => ({ user, loading, refresh, register, login, logoutToGuest }),
    [user, loading, refresh, register, login, logoutToGuest],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used within SessionProvider')
  return ctx
}
