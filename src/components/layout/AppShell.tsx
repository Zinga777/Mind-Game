import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { clsx } from 'clsx'

const NAV_ITEMS = [
  { to: '/', label: 'Home', icon: '⌂' },
  { to: '/pre-game', label: 'Play', icon: '▶' },
  { to: '/leaderboard', label: 'Ranks', icon: '⚑' },
  { to: '/profile', label: 'Profile', icon: '◉' },
]

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex min-h-screen w-full max-w-[560px] flex-col bg-ink-950">
      <header className="hidden items-center justify-between border-b border-ink-800 px-6 py-4 sm:flex">
        <div className="text-sm font-bold tracking-[0.2em] text-ink-50">MIND ATHLETE</div>
        <nav className="flex gap-1">
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
        </nav>
      </header>

      <main className="flex-1 px-4 pb-24 pt-6 sm:pb-6">{children}</main>

      <nav className="fixed inset-x-0 bottom-0 mx-auto flex w-full max-w-[560px] border-t border-ink-800 bg-ink-900/95 backdrop-blur sm:hidden">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              clsx(
                'flex flex-1 flex-col items-center gap-1 py-3 text-[11px] font-semibold uppercase tracking-wide',
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
