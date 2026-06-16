import { forwardRef, type TextareaHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        'w-full rounded-lg border bg-surface-2/50 px-3 py-2.5 text-sm text-text resize-y',
        'placeholder:text-muted/60',
        'transition-all duration-200',
        'focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/40 focus:bg-surface-2',
        'hover:border-border',
        error
          ? 'border-danger/50 focus:ring-danger/30 focus:border-danger/40'
          : 'border-border-subtle',
        className
      )}
      {...props}
    />
  )
)
Textarea.displayName = 'Textarea'
