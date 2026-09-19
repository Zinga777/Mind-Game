import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Button } from '../ui/Button'
import { claimAdReward } from '../../lib/profileApi'
import { ApiError } from '../../lib/api'

const AD_DURATION_S = 5

/**
 * No real ad network is wired up in this build — this is the AdService
 * abstraction's local "house" provider: a clearly-labeled, timed placeholder
 * that plays instead of a real creative. Swapping in a real network later
 * means implementing this same interface (show → wait for completion →
 * call the reward endpoint), not touching any caller.
 */
export function RewardedAdModal({
  open,
  onClose,
  onRewarded,
}: {
  open: boolean
  onClose: () => void
  onRewarded: (coins: number) => void
}) {
  const [secondsLeft, setSecondsLeft] = useState(AD_DURATION_S)
  const [state, setState] = useState<'playing' | 'claiming' | 'rewarded' | 'error'>('playing')
  const [error, setError] = useState<string | null>(null)
  const [rewardCoins, setRewardCoins] = useState(0)

  useEffect(() => {
    if (!open) {
      setSecondsLeft(AD_DURATION_S)
      setState('playing')
      setError(null)
      return
    }
    if (secondsLeft <= 0) return
    const t = setTimeout(() => setSecondsLeft((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [open, secondsLeft])

  useEffect(() => {
    if (open && secondsLeft === 0 && state === 'playing') {
      setState('claiming')
      claimAdReward('post_game_reward')
        .then((res) => {
          setRewardCoins(res.rewardCoins)
          setState('rewarded')
          onRewarded(res.rewardCoins)
        })
        .catch((err) => {
          setState('error')
          setError(err instanceof ApiError ? err.message : 'Could not reach the server')
        })
    }
  }, [open, secondsLeft, state, onRewarded])

  useEffect(() => {
    if (state !== 'rewarded') return
    const t = setTimeout(onClose, 1400)
    return () => clearTimeout(t)
  }, [state, onClose])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4"
        >
          <motion.div
            initial={{ scale: 0.92, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.92, opacity: 0 }}
            className="w-full max-w-sm rounded-2xl border border-ink-700 bg-ink-850 p-6 text-center"
          >
            {state === 'error' ? (
              <>
                <div className="text-sm font-semibold text-danger-500">Ad reward failed</div>
                <p className="mt-2 text-xs text-ink-400">{error}</p>
                <Button variant="secondary" className="mt-4 w-full" onClick={onClose}>
                  CLOSE
                </Button>
              </>
            ) : state === 'rewarded' ? (
              <>
                <div className="text-3xl">✓</div>
                <div className="mt-2 text-lg font-bold text-focus-400">+{rewardCoins} coins</div>
                <p className="mt-1 text-xs text-ink-400">Reward credited</p>
              </>
            ) : (
              <>
                <div className="text-xs font-semibold uppercase tracking-wider text-ink-400">Placeholder Ad</div>
                <div className="mt-4 flex aspect-video items-center justify-center rounded-xl border border-dashed border-ink-600 bg-ink-900">
                  <span className="text-ink-500">Sponsored break</span>
                </div>
                <div className="mt-4 text-3xl font-black tabular-nums text-focus-400">
                  {state === 'claiming' ? '…' : secondsLeft}
                </div>
                <p className="mt-2 text-xs text-ink-400">
                  {state === 'claiming' ? 'Crediting your reward…' : 'Reward unlocks when this ad finishes'}
                </p>
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
