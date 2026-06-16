import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '../../lib/cn'

type Variant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'primary'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant
  children: ReactNode
  dot?: boolean
}

const variants: Record<Variant, string> = {
  default: 'bg-surface-2 text-muted border-border',
  success: 'bg-success/10 text-success border-success/20',
  warning: 'bg-warning/10 text-warning border-warning/20',
  danger: 'bg-danger/10 text-danger border-danger/20',
  info: 'bg-info/10 text-info border-info/20',
  primary: 'bg-primary-muted text-primary border-primary/20',
}

const dotColors: Record<Variant, string> = {
  default: 'bg-muted',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
  info: 'bg-info',
  primary: 'bg-primary',
}

export function Badge({ variant = 'default', className, children, dot, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        'transition-colors duration-200',
        variants[variant],
        className
      )}
      {...props}
    >
      {dot && (
        <span className={cn('h-1.5 w-1.5 rounded-full animate-breathe', dotColors[variant])} />
      )}
      {children}
    </span>
  )
}
