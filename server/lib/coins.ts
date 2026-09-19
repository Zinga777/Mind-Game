import { db } from '../db'
import { newId } from './ids'

export type CoinLedgerType = 'EARNED' | 'SPENT' | 'ADJUSTED'

/**
 * The only way coins ever move. Always reads the current balance from the
 * wallet row, writes the new balance, and appends an auditable ledger entry
 * in one transaction — a client can never set `amount` or a resulting
 * balance directly.
 */
export const applyCoinTransaction = db.transaction(
  (userId: string, type: CoinLedgerType, amount: number, source: string, referenceId?: string) => {
    const wallet = db.prepare('SELECT balance FROM coin_wallets WHERE user_id = ?').get(userId) as
      | { balance: number }
      | undefined
    const balanceBefore = wallet?.balance ?? 0

    if (!wallet) {
      db.prepare('INSERT INTO coin_wallets (user_id, balance) VALUES (?, 0)').run(userId)
    }

    const signedAmount = type === 'SPENT' ? -Math.abs(amount) : Math.abs(amount)
    const balanceAfter = Math.max(0, balanceBefore + signedAmount)

    db.prepare('UPDATE coin_wallets SET balance = ? WHERE user_id = ?').run(balanceAfter, userId)
    db.prepare(
      `INSERT INTO coin_ledger (id, user_id, type, amount, balance_before, balance_after, source, reference_id, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(newId('ledger'), userId, type, signedAmount, balanceBefore, balanceAfter, source, referenceId ?? null, Date.now())

    return balanceAfter
  },
)

export function getWalletBalance(userId: string): number {
  const wallet = db.prepare('SELECT balance FROM coin_wallets WHERE user_id = ?').get(userId) as
    | { balance: number }
    | undefined
  return wallet?.balance ?? 0
}
