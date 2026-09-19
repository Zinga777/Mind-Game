import type { ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { clsx } from 'clsx'
import { motion, AnimatePresence } from 'framer-motion'
import { useSession } from '../../state/SessionContext'

const NAV_ITEMS = [
  { to: '/', label: 'Home', icon: '⌂' },
  { to: '/pre-game', label: 'Play', icon: '▶' },
  { to: '/leaderboard', label: 'Ranks', icon: '⚑' },
  { to: '/tournaments', label: 'Cups', icon: '☖' },
  { to: '/profile', label: 'Profile', icon: '◉' },
]

function CoinBalance() {
  const { user } = useSession()
  if (!user) return null
  return (
    <div className="flex items-center gap-1.5 rounded-full border border-ink-700 bg-ink-800/60 px-3 py-1 text-xs font-bold text-ember-400">
      <span>◈</span>
      <span className="tabular-nums">{user.coins.toLocaleString()}</span>
    </div>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation()

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-[560px] flex-col bg-ink-950">
      <header className="hidden items-center justify-between border-b border-ink-800 px-6 py-4 sm:flex">
        <div className="text-sm font-bold tracking-[0.2em] text-ink-50">MIND ATHLETE</div>
        <nav className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  'rounded-lg px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-colors',
                  isActive ? 'bg-ink-800 text-focus-400' : 'text-ink-300 hover:text-ink-50',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
          <div className="ml-2">
            <CoinBalance />
          </div>
        </nav>
      </header>

      <div className="flex items-center justify-between px-4 pt-4 sm:hidden">
        <div className="text-xs font-bold tracking-[0.2em] text-ink-50">MIND ATHLETE</div>
        <CoinBalance />
      </div>

      <main className="flex-1 px-4 pb-24 pt-4 sm:pb-6">
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

      <nav className="fixed inset-x-0 bottom-0 mx-auto flex w-full max-w-[560px] border-t border-ink-800 bg-ink-900/95 backdrop-blur sm:hidden">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              clsx(
                'flex flex-1 flex-col items-center gap-1 py-3 text-[10px] font-semibold uppercase tracking-wide',
                isActive ? 'text-focus-400' : 'text-ink-400',
              )
            }
          >
            <span className="text-lg leading-none">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
