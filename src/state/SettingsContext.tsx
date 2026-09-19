import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { SettingsRepository } from '../repositories/SettingsRepository'
import type { SettingsRecord } from '../data/db'

interface SettingsContextValue {
  settings: SettingsRecord | null
  update: (patch: Partial<Omit<SettingsRecord, 'id'>>) => Promise<void>
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<SettingsRecord | null>(null)

  useEffect(() => {
    SettingsRepository.get().then(setSettings)
  }, [])

  const update = useCallback(async (patch: Partial<Omit<SettingsRecord, 'id'>>) => {
    const next = await SettingsRepository.update(patch)
    setSettings(next)
  }, [])

  const value = useMemo(() => ({ settings, update }), [settings, update])
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}
