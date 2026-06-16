import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { CheckCircle, AlertTriangle, XCircle, Info, X } from 'lucide-react'
import { cn } from '../../lib/cn'

type ToastVariant = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: string
  variant: ToastVariant
  title: string
  description?: string
}

interface ToastContextValue {
  toast: (variant: ToastVariant, title: string, description?: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const icons: Record<ToastVariant, typeof CheckCircle> = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const colors: Record<ToastVariant, string> = {
  success: 'text-success border-success/20',
  error: 'text-danger border-danger/20',
  warning: 'text-warning border-warning/20',
  info: 'text-info border-info/20',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((variant: ToastVariant, title: string, description?: string) => {
    const id = Math.random().toString(36).slice(2)
    setToasts((prev) => [...prev, { id, variant, title, description }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4000)
  }, [])

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => {
          const Icon = icons[t.variant]
          return (
            <div
              key={t.id}
              className={cn(
                'pointer-events-auto flex items-start gap-3 rounded-xl border p-4 pr-3 min-w-[320px] max-w-[420px]',
                'glass shadow-lg',
                colors[t.variant]
              )}
              style={{ animation: 'slideToast 300ms cubic-bezier(0.34, 1.56, 0.64, 1)' }}
            >
              <Icon size={18} className="shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text">{t.title}</p>
                {t.description && (
                  <p className="text-xs text-muted mt-0.5">{t.description}</p>
                )}
              </div>
              <button
                onClick={() => removeToast(t.id)}
                className="shrink-0 p-1 rounded-md text-muted hover:text-text hover:bg-surface-2/50 transition-colors"
              >
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
