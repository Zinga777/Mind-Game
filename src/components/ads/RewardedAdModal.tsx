import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Button } from '../ui/Button'
import { LightningBolt } from '../brand/LightningMark'
import { adService } from '../../services/AdService'
import { AdFrequencyManager } from '../../services/AdFrequencyManager'
import { DEFAULT_THUNDER_CONFIG } from '../../game-engine/thunder'

const AD_DURATION_S = 5

/**
 * No real ad network is wired up in this build — this is the AdService
 * abstraction's local "house" provider: a clearly-labeled, timed placeholder
 * that plays instead of a real creative. Swapping in a real network later
 * means implementing AdService for real, not touching any caller.
 */
export function RewardedAdModal({
  open,
  onClose,
  onRewarded,
}: {
  open: boolean
  onClose: () => void
  onRewarded: (thunder: number) => void
}) {
  const [secondsLeft, setSecondsLeft] = useState(AD_DURATION_S)
  const [state, setState] = useState<'playing' | 'claiming' | 'rewarded' | 'unavailable'>('playing')

  useEffect(() => {
    if (!open) {
      setSecondsLeft(AD_DURATION_S)
      setState('playing')
      return
    }
    adService.isRewardedAdAvailable().then((available) => {
      if (!available) setState('unavailable')
    })
  }, [open])

  useEffect(() => {
    if (!open || state !== 'playing' || secondsLeft <= 0) return
    const t = setTimeout(() => setSecondsLeft((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [open, secondsLeft, state])

  useEffect(() => {
    if (open && secondsLeft === 0 && state === 'playing') {
      setState('claiming')
      adService.showRewardedThunderAd().then(async (result) => {
        if (!result.watched) {
          setState('unavailable')
          return
        }
        await AdFrequencyManager.recordRewardedAdWatched()
        setState('rewarded')
        onRewarded(DEFAULT_THUNDER_CONFIG.rewardedAdAmount)
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
            {state === 'unavailable' ? (
              <>
                <div className="text-sm font-semibold text-ink-100">Ad unavailable</div>
                <p className="mt-2 text-xs text-ink-400">
                  {navigator.onLine ? "No ad to show right now — try again shortly." : 'No network connection — rewarded ads need a connection.'}
                </p>
                <Button variant="secondary" className="mt-4 w-full" onClick={onClose}>
                  CLOSE
                </Button>
              </>
            ) : state === 'rewarded' ? (
              <>
                <LightningBolt className="mx-auto h-8 w-8" />
                <div className="mt-2 text-lg font-bold text-volt-400">+{DEFAULT_THUNDER_CONFIG.rewardedAdAmount} Thunder</div>
                <p className="mt-1 text-xs text-ink-400">Reward credited</p>
              </>
            ) : (
              <>
                <div className="text-xs font-semibold uppercase tracking-wider text-ink-400">Placeholder Ad</div>
                <div className="mt-4 flex aspect-video items-center justify-center rounded-xl border border-dashed border-ink-600 bg-ink-900">
                  <span className="text-ink-500">Sponsored break</span>
                </div>
                <div className="mt-4 text-3xl font-black tabular-nums text-volt-400">
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
