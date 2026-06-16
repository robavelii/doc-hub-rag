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
        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none">
          {icon}
        </div>
      )}
      <input
        ref={ref}
        className={cn(
          'w-full rounded-lg border bg-surface-2/50 px-3 py-2.5 text-sm text-text',
          'placeholder:text-muted/60',
          'transition-all duration-200',
          'focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/40 focus:bg-surface-2',
          'hover:border-border',
          error
            ? 'border-danger/50 focus:ring-danger/30 focus:border-danger/40'
            : 'border-border-subtle',
          icon ? 'pl-10' : '',
          className
        )}
        {...props}
      />
    </div>
  )
)
Input.displayName = 'Input'
