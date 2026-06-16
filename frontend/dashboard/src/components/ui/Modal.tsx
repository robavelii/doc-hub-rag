import { useEffect, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { cn } from '../../lib/cn'
import { IconButton } from './IconButton'

interface ModalProps {
  open: boolean
  onClose: () => void
  children: ReactNode
  title?: string
  description?: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizes = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
}

export function Modal({ open, onClose, children, title, description, size = 'md', className }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleEsc)
    document.body.style.overflow = 'hidden'
    dialogRef.current?.focus()
    return () => {
      document.removeEventListener('keydown', handleEsc)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose()
      }}
      style={{ animation: 'modalBackdrop 250ms ease-out forwards' }}
    >
      <div className="absolute inset-0 bg-black/50" aria-hidden="true" />

      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? 'modal-title' : undefined}
        aria-describedby={description ? 'modal-description' : undefined}
        tabIndex={-1}
        className={cn(
          'relative w-full rounded-2xl p-6',
          'glass shadow-lg',
          'animate-scale-in',
          sizes[size],
          className
        )}
      >
        {(title || true) && (
          <div className="flex items-start justify-between mb-4">
            <div>
              {title && (
                <h2 id="modal-title" className="text-lg font-semibold text-text">
                  {title}
                </h2>
              )}
              {description && (
                <p id="modal-description" className="text-sm text-muted mt-1">
                  {description}
                </p>
              )}
            </div>
            <IconButton label="Close dialog" onClick={onClose} className="-mr-1 -mt-1">
              <X size={18} />
            </IconButton>
          </div>
        )}

        {children}
      </div>
    </div>
  )
}
