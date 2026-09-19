import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { PlayerRepository } from '../repositories/PlayerRepository'
import type { PlayerProfileRecord } from '../data/db'

interface PlayerContextValue {
  profile: PlayerProfileRecord | null
  loading: boolean
  updateUsername: (username: string) => Promise<void>
  updateAvatar: (avatarId: string) => Promise<void>
}

const PlayerContext = createContext<PlayerContextValue | null>(null)

export function PlayerProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<PlayerProfileRecord | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    PlayerRepository.getOrCreate()
      .then(setProfile)
      .finally(() => setLoading(false))
  }, [])

  const updateUsername = useCallback(async (username: string) => {
    const next = await PlayerRepository.updateUsername(username)
    setProfile(next)
  }, [])

  const updateAvatar = useCallback(async (avatarId: string) => {
    const next = await PlayerRepository.updateAvatar(avatarId)
    setProfile(next)
  }, [])

  const value = useMemo(() => ({ profile, loading, updateUsername, updateAvatar }), [profile, loading, updateUsername, updateAvatar])

  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>
}

export function usePlayer(): PlayerContextValue {
  const ctx = useContext(PlayerContext)
  if (!ctx) throw new Error('usePlayer must be used within PlayerProvider')
  return ctx
}
