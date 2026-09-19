import { getDb } from '../data/db'

export const AchievementRepository = {
  async getUnlocked(): Promise<Set<string>> {
    const db = await getDb()
    const all = await db.getAll('achievements')
    return new Set(all.map((a) => a.id))
  },

  async unlock(id: string): Promise<boolean> {
    const db = await getDb()
    const existing = await db.get('achievements', id)
    if (existing) return false
    await db.put('achievements', { id, unlockedAt: Date.now() })
    return true
  },
}
