import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { useSession } from '../../state/SessionContext'

export function SplashGate({ children }: { children: ReactNode }) {
  const { loading } = useSession()

  if (!loading) return <>{children}</>

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-ink-950">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.3 }}
        className="text-lg font-bold tracking-[0.3em] text-ink-50"
      >
        MIND ATHLETE
      </motion.div>
      <div className="h-1 w-32 overflow-hidden rounded-full bg-ink-800">
        <motion.div
          className="h-full w-1/3 rounded-full bg-focus-500"
          animate={{ x: ['-100%', '300%'] }}
          transition={{ repeat: Infinity, duration: 1.1, ease: 'easeInOut' }}
        />
      </div>
    </div>
  )
}
