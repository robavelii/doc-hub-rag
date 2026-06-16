import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '../../lib/cn'

type CardVariant = 'default' | 'glass'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  variant?: CardVariant
}

export function Card({ className, children, variant = 'default', ...props }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl p-5 animate-fade-in',
        variant === 'glass'
          ? 'glass shadow-md'
          : 'bg-surface border border-border shadow-sm',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ className, children, ...props }: Omit<CardProps, 'variant'>) {
  return (
    <div className={cn('mb-4 flex items-center justify-between', className)} {...props}>
      {children}
    </div>
  )
}

export function CardTitle({ className, children, ...props }: Omit<CardProps, 'variant'>) {
  return (
    <h3 className={cn('text-base font-semibold text-text', className)} {...props}>
      {children}
    </h3>
  )
}

export function CardDescription({ className, children, ...props }: Omit<CardProps, 'variant'>) {
  return (
    <p className={cn('text-sm text-muted mt-1', className)} {...props}>
      {children}
    </p>
  )
}
