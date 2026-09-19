import { getDb } from '../data/db'
import type { SettingsRecord } from '../data/db'

const DEFAULTS: SettingsRecord = {
  id: 'singleton',
  sfxEnabled: true,
  musicEnabled: true,
  hapticsEnabled: true,
  reduceMotion: false,
  masterVolume: 0.7,
}

export const SettingsRepository = {
  async get(): Promise<SettingsRecord> {
    const db = await getDb()
    const existing = await db.get('settings', 'singleton')
    return existing ?? DEFAULTS
  },

  async update(patch: Partial<Omit<SettingsRecord, 'id'>>): Promise<SettingsRecord> {
    const db = await getDb()
    const current = await this.get()
    const next = { ...current, ...patch }
    await db.put('settings', next)
    return next
  },
}
