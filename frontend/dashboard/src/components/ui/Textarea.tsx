import { forwardRef, type TextareaHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, ...props }, ref) => (
    <textarea
      ref={ref}
      aria-invalid={error || undefined}
      className={cn(
        'w-full resize-y rounded-lg border bg-surface px-3 py-2.5 text-sm text-text shadow-sm',
        'placeholder:text-muted/70',
        'transition-[border-color] duration-micro ease-out',
        'hover:border-muted focus:border-focus',
        'disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-muted',
        error ? 'border-danger' : 'border-field',
        className
      )}
      {...props}
    />
  )
)
Textarea.displayName = 'Textarea'
