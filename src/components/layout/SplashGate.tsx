import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { LightningBolt } from '../brand/LightningMark'
import { usePlayer } from '../../state/PlayerContext'
import { useThunder } from '../../state/ThunderContext'

export function SplashGate({ children }: { children: ReactNode }) {
  const { loading: playerLoading } = usePlayer()
  const { loading: thunderLoading } = useThunder()

  if (!playerLoading && !thunderLoading) return <>{children}</>

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-ink-950">
      <motion.div initial={{ opacity: 0, scale: 0.85 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.3 }}>
        <LightningBolt className="h-12 w-12" />
      </motion.div>
      <div className="text-sm font-bold tracking-[0.3em] text-ink-50">MIND ATHLETE</div>
      <div className="h-1 w-32 overflow-hidden rounded-full bg-ink-800">
        <motion.div
          className="h-full w-1/3 rounded-full bg-volt-500"
          animate={{ x: ['-100%', '300%'] }}
          transition={{ repeat: Infinity, duration: 1.1, ease: 'easeInOut' }}
        />
      </div>
    </div>
  )
}
