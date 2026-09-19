import { getDb } from '../data/db'
import { newId } from '../data/ids'
import type { ThunderTransactionRecord, ThunderTransactionType } from '../data/db'

/**
 * The only way the Thunder balance ever changes. Balance is derived by
 * folding the ledger rather than stored as a separately-mutable number, so
 * it can never drift from its own history — the same principle a
 * server-authoritative wallet would use, just running locally.
 *
 * `dedupeKey` guards against double-claiming the same reward (e.g. a
 * rewarded-ad callback firing twice, or a result screen re-submitting on
 * re-render): if a transaction with that key already exists, the request
 * is a no-op and returns the existing balance.
 */
export const ThunderRepository = {
  async getBalance(): Promise<number> {
    const db = await getDb()
    const all = await db.getAll('thunderLedger')
    return all.reduce((sum, tx) => sum + tx.amount, 0)
  },

  async getHistory(limit = 50): Promise<ThunderTransactionRecord[]> {
    const db = await getDb()
    const all = await db.getAllFromIndex('thunderLedger', 'byTimestamp')
    return all.reverse().slice(0, limit)
  },

  async apply(params: {
    type: ThunderTransactionType
    amount: number
    source: string
    challengeId?: string
    dedupeKey?: string
  }): Promise<{ balance: number; applied: boolean }> {
    const db = await getDb()

    const current = await this.getBalance()
    const signedAmount = params.type === 'SPENT' ? -Math.abs(params.amount) : Math.abs(params.amount)
    const balanceAfter = Math.max(0, current + signedAmount)

    const record: ThunderTransactionRecord = {
      transactionId: newId('thunder'),
      timestamp: Date.now(),
      type: params.type,
      amount: signedAmount,
      balanceAfter,
      source: params.source,
      challengeId: params.challengeId,
      dedupeKey: params.dedupeKey,
    }

    try {
      // `add` (not `put`) so the unique dedupeKey index rejects a second
      // write for the same key instead of silently overwriting or racing —
      // closes the check-then-write race a check-first approach would have.
      await db.add('thunderLedger', record)
      return { balance: balanceAfter, applied: true }
    } catch (err) {
      if (params.dedupeKey && err instanceof DOMException && err.name === 'ConstraintError') {
        const balance = await this.getBalance()
        return { balance, applied: false }
      }
      throw err
    }
  },

  /** Fails (without writing) if the player can't afford the cost, instead of ever letting balance go negative. */
  async spend(amount: number, source: string, challengeId?: string): Promise<{ ok: boolean; balance: number }> {
    const balance = await this.getBalance()
    if (balance < amount) return { ok: false, balance }
    const result = await this.apply({ type: 'SPENT', amount, source, challengeId })
    return { ok: true, balance: result.balance }
  },
}
