import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string
  size?: 'sm' | 'md' | 'lg'
}

const sizes = {
  sm: 'p-1',
  md: 'p-1.5',
  lg: 'p-2',
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ className, label, size = 'md', children, ...props }, ref) => (
    <button
      ref={ref}
      type="button"
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex items-center justify-center rounded-lg text-muted',
        'hover:bg-surface-2/80 hover:text-text',
        'active:scale-95',
        'transition-all duration-150',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
    </button>
  )
)
IconButton.displayName = 'IconButton'
