import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'gradient'
type Size = 'sm' | 'md' | 'lg' | 'icon'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
}

const variants: Record<Variant, string> = {
  primary:
    'bg-primary text-white hover:bg-primary-hover shadow-sm hover:shadow-glow active:scale-[0.98]',
  secondary:
    'glass text-text hover:bg-surface-2 active:scale-[0.98]',
  ghost:
    'bg-transparent text-muted hover:text-text hover:bg-surface-2/50',
  danger:
    'bg-danger/10 text-danger border border-danger/20 hover:bg-danger/20 active:scale-[0.98]',
  gradient:
    'bg-gradient-to-r from-primary to-accent-blue text-white shadow-sm hover:shadow-glow active:scale-[0.98]',
}

const sizes: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-xs gap-1.5',
  md: 'px-4 py-2 text-sm gap-2',
  lg: 'px-5 py-2.5 text-sm gap-2',
  icon: 'p-2',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', loading, disabled, children, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center rounded-lg font-medium',
        'transition-all duration-200 ease-out',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
        'disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {loading && <Loader2 size={size === 'sm' ? 14 : 16} className="animate-spin-slow" />}
      {children}
    </button>
  )
)
Button.displayName = 'Button'
