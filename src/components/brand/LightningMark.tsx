import type { CSSProperties } from 'react'
import { clsx } from 'clsx'

/**
 * The Mind Athlete lightning identity — a single vector bolt used
 * consistently across the wordmark, icon-only mark, favicon, and PWA
 * icons, so there's one shape to recognize rather than a generic emoji
 * standing in for a logo.
 */
export function LightningBolt({
  className,
  monochrome,
  style,
}: {
  className?: string
  monochrome?: boolean
  style?: CSSProperties
}) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} style={style} aria-hidden="true">
      <path
        d="M13.2 2 4.5 13.6c-.32.43-.02 1.05.52 1.05h5.1l-1.3 7.3c-.12.68.72 1.07 1.16.53L18.8 10.4c.34-.42.03-1.05-.51-1.05h-5.2l1.31-6.75c.13-.68-.7-1.1-1.2-.6Z"
        fill={monochrome ? 'currentColor' : 'url(#volt-gradient)'}
        stroke={monochrome ? 'currentColor' : 'none'}
        strokeWidth={monochrome ? 0 : 0}
      />
      {!monochrome && (
        <defs>
          <linearGradient id="volt-gradient" x1="4" y1="2" x2="20" y2="22" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#6dff96" />
            <stop offset="100%" stopColor="#1fd94e" />
          </linearGradient>
        </defs>
      )}
    </svg>
  )
}

export function LightningWordmark({ className }: { className?: string }) {
  return (
    <div className={clsx('flex items-center gap-2', className)}>
      <LightningBolt className="h-5 w-5 shrink-0" />
      <span className="text-sm font-bold tracking-[0.2em] text-ink-50">MIND ATHLETE</span>
    </div>
  )
}
