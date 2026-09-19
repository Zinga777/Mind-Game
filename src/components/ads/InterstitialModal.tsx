import { AnimatePresence, motion } from 'framer-motion'
import { Button } from '../ui/Button'

/**
 * Shown only at the natural transition after Results → Home, gated by
 * AdFrequencyManager (game-count cooldown, time cooldown, new-player
 * protection). Never appears during gameplay, never blocks the player from
 * seeing their score/PB/Thunder first.
 */
export function InterstitialModal({ open, onDismiss }: { open: boolean; onDismiss: () => void }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 px-4"
        >
          <motion.div
            initial={{ scale: 0.92, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.92, opacity: 0 }}
            className="w-full max-w-sm rounded-2xl border border-ink-700 bg-ink-850 p-6 text-center"
          >
            <div className="text-xs font-semibold uppercase tracking-wider text-ink-400">Placeholder Ad</div>
            <div className="mt-4 flex aspect-video items-center justify-center rounded-xl border border-dashed border-ink-600 bg-ink-900">
              <span className="text-ink-500">Sponsored break</span>
            </div>
            <Button variant="secondary" className="mt-4 w-full" onClick={onDismiss}>
              CONTINUE
            </Button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
