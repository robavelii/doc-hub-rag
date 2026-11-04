import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center px-6 py-14 text-center',
        className
      )}
    >
      {icon && (
        <div className="mb-4 text-muted" aria-hidden="true">
          {icon}
        </div>
      )}
      <h3 className="mb-1 text-base font-semibold text-text">{title}</h3>
      {description && (
        <p className="mb-5 max-w-sm text-sm text-muted">{description}</p>
      )}
      {action}
    </div>
  )
}
