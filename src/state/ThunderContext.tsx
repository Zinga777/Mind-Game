import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ThunderRepository } from '../repositories/ThunderRepository'
import { DEFAULT_THUNDER_CONFIG } from '../game-engine/thunder'
import type { ThunderTransactionType } from '../data/db'

interface ThunderContextValue {
  balance: number
  loading: boolean
  refresh: () => Promise<void>
  spend: (amount: number, source: string, challengeId?: string) => Promise<boolean>
  earn: (amount: number, source: string, dedupeKey?: string) => Promise<void>
  apply: (type: ThunderTransactionType, amount: number, source: string, dedupeKey?: string) => Promise<void>
}

const ThunderContext = createContext<ThunderContextValue | null>(null)

export function ThunderProvider({ children }: { children: ReactNode }) {
  const [balance, setBalance] = useState(0)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    const current = await ThunderRepository.getBalance()
    setBalance(current)
  }, [])

  useEffect(() => {
    ;(async () => {
      // First launch: grant the starting balance so a new player never hits
      // a paywall before understanding the product. The dedupeKey makes
      // this a no-op (returns the real current balance) on every later
      // load, even if the player has since spent down to 0.
      const { balance: current } = await ThunderRepository.apply({
        type: 'EARNED',
        amount: DEFAULT_THUNDER_CONFIG.startingBalance,
        source: 'welcome_grant',
        dedupeKey: 'welcome_grant',
      })
      setBalance(current)
      setLoading(false)
    })()
  }, [])

  const spend = useCallback(async (amount: number, source: string, challengeId?: string) => {
    const result = await ThunderRepository.spend(amount, source, challengeId)
    setBalance(result.balance)
    return result.ok
  }, [])

  const earn = useCallback(async (amount: number, source: string, dedupeKey?: string) => {
    const result = await ThunderRepository.apply({ type: 'EARNED', amount, source, dedupeKey })
    setBalance(result.balance)
  }, [])

  const apply = useCallback(async (type: ThunderTransactionType, amount: number, source: string, dedupeKey?: string) => {
    const result = await ThunderRepository.apply({ type, amount, source, dedupeKey })
    setBalance(result.balance)
  }, [])

  const value = useMemo(() => ({ balance, loading, refresh, spend, earn, apply }), [balance, loading, refresh, spend, earn, apply])

  return <ThunderContext.Provider value={value}>{children}</ThunderContext.Provider>
}

export function useThunder(): ThunderContextValue {
  const ctx = useContext(ThunderContext)
  if (!ctx) throw new Error('useThunder must be used within ThunderProvider')
  return ctx
}
