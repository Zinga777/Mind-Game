import type { HTMLAttributes, ReactNode } from 'react'
import { clsx } from 'clsx'

export function Card({ className, children, ...rest }: HTMLAttributes<HTMLDivElement> & { children: ReactNode }) {
  return (
    <div
      className={clsx('rounded-2xl border border-ink-700 bg-ink-850/80 p-5 backdrop-blur-sm', className)}
      {...rest}
    >
      {children}
    </div>
  )
}

export function StatTile({ label, value, accent }: { label: string; value: ReactNode; accent?: boolean }) {
  return (
    <div className="rounded-xl bg-ink-800/60 px-4 py-3">
      <div className="text-xs uppercase tracking-wider text-ink-300">{label}</div>
      <div className={clsx('mt-1 text-xl font-bold tabular-nums', accent ? 'text-volt-400' : 'text-ink-50')}>
        {value}
      </div>
    </div>
  )
}

export function Badge({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'volt' | 'thunder' }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider',
        tone === 'default' && 'bg-ink-800 text-ink-200',
        tone === 'volt' && 'bg-volt-500/15 text-volt-400',
        tone === 'thunder' && 'bg-thunder-500/15 text-thunder-400',
      )}
    >
      {children}
    </span>
  )
}
