import { type ButtonHTMLAttributes, type ReactNode } from 'react'
import { clsx } from 'clsx'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'md' | 'lg'
  children: ReactNode
}

export function Button({ variant = 'primary', size = 'md', className, children, ...rest }: ButtonProps) {
  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-xl font-semibold tracking-wide transition-transform duration-150 active:scale-[0.97] disabled:opacity-40 disabled:pointer-events-none',
        size === 'md' ? 'px-5 py-3 text-sm' : 'px-8 py-4 text-base',
        variant === 'primary' && 'bg-volt-500 text-ink-950 hover:bg-volt-400 shadow-[0_0_0_1px_rgba(51,230,201,0.3)]',
        variant === 'secondary' && 'bg-ink-800 text-ink-50 hover:bg-ink-700 border border-ink-600',
        variant === 'ghost' && 'bg-transparent text-ink-200 hover:text-ink-50 hover:bg-ink-800',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}
