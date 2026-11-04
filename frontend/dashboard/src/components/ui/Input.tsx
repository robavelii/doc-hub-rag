import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: boolean
  icon?: React.ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, icon, ...props }, ref) => (
    <div className="relative">
      {icon && (
        <div className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted">
          {icon}
        </div>
      )}
      <input
        ref={ref}
        aria-invalid={error || undefined}
        className={cn(
          'h-10 w-full rounded-lg border bg-surface px-3 text-sm text-text shadow-sm',
          'placeholder:text-muted/70',
          'transition-[border-color] duration-micro ease-out',
          'hover:border-muted focus:border-focus',
          'disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-muted',
          'read-only:bg-surface-2',
          error ? 'border-danger' : 'border-field',
          icon ? 'pl-9' : '',
          className
        )}
        {...props}
      />
    </div>
  )
)
Input.displayName = 'Input'
