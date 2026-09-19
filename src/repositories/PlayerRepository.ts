import { getDb } from '../data/db'
import type { PlayerProfileRecord } from '../data/db'

const ADJECTIVES = ['Swift', 'Sharp', 'Bright', 'Bold', 'Quick', 'Calm', 'Keen', 'Prime']
const NOUNS = ['Athlete', 'Mind', 'Scanner', 'Strategist', 'Adapter', 'Sprinter']
const AVATAR_IDS = ['bolt-01', 'bolt-02', 'bolt-03', 'bolt-04', 'bolt-05', 'bolt-06']

function randomName(): string {
  const adj = ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)]
  const noun = NOUNS[Math.floor(Math.random() * NOUNS.length)]
  return `${adj}${noun}${Math.floor(10 + Math.random() * 90)}`
}

export const PlayerRepository = {
  async getOrCreate(): Promise<PlayerProfileRecord> {
    const db = await getDb()
    const existing = await db.get('profile', 'singleton')
    if (existing) return existing

    const profile: PlayerProfileRecord = {
      id: 'singleton',
      username: randomName(),
      avatarId: AVATAR_IDS[Math.floor(Math.random() * AVATAR_IDS.length)],
      createdAt: Date.now(),
    }
    await db.put('profile', profile)
    return profile
  },

  async updateUsername(username: string): Promise<PlayerProfileRecord> {
    const db = await getDb()
    const existing = await this.getOrCreate()
    const next = { ...existing, username }
    await db.put('profile', next)
    return next
  },

  async updateAvatar(avatarId: string): Promise<PlayerProfileRecord> {
    const db = await getDb()
    const existing = await this.getOrCreate()
    const next = { ...existing, avatarId }
    await db.put('profile', next)
    return next
  },

  AVATAR_IDS,
}
