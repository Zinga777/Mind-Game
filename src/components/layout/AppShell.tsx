import type { ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { clsx } from 'clsx'
import { motion, AnimatePresence } from 'framer-motion'
import { LightningBolt, LightningWordmark } from '../brand/LightningMark'
import { useThunder } from '../../state/ThunderContext'

const NAV_ITEMS = [
  { to: '/', label: 'Home', icon: '⌂' },
  { to: '/pre-game', label: 'Play', icon: '▶' },
  { to: '/profile', label: 'Profile', icon: '◉' },
]

function ThunderBalance() {
  const { balance, loading } = useThunder()
  return (
    <div className="flex items-center gap-1.5 rounded-full border border-ink-700 bg-ink-800/60 px-3 py-1 text-xs font-bold text-thunder-400">
      <LightningBolt className="h-3.5 w-3.5" />
      <span className="tabular-nums">{loading ? '—' : balance.toLocaleString()}</span>
    </div>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation()
  const hideChrome = location.pathname === '/play'

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-[560px] flex-col bg-ink-950">
      {!hideChrome && (
        <>
          <header className="hidden items-center justify-between border-b border-ink-800 px-6 py-4 sm:flex">
            <LightningWordmark />
            <nav className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    clsx(
                      'rounded-lg px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-colors',
                      isActive ? 'bg-ink-800 text-volt-400' : 'text-ink-300 hover:text-ink-50',
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
              <div className="ml-2">
                <ThunderBalance />
              </div>
            </nav>
          </header>

          <div className="flex items-center justify-between px-4 pt-4 sm:hidden">
            <LightningWordmark className="text-xs" />
            <ThunderBalance />
          </div>
        </>
      )}

      <main className={clsx('flex-1 px-4', hideChrome ? 'pb-4 pt-4' : 'pb-24 pt-4 sm:pb-6')}>
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>

      {!hideChrome && (
        <nav className="fixed inset-x-0 bottom-0 mx-auto flex w-full max-w-[560px] border-t border-ink-800 bg-ink-900/95 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:hidden">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  'flex flex-1 flex-col items-center gap-1 py-3 text-[10px] font-semibold uppercase tracking-wide',
                  isActive ? 'text-volt-400' : 'text-ink-400',
                )
              }
            >
              <span className="text-lg leading-none">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
      )}
    </div>
  )
}
