import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface DropdownProps {
  trigger: ReactNode
  children: ReactNode
  align?: 'left' | 'right'
  className?: string
}

export function Dropdown({ trigger, children, align = 'right', className }: DropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  return (
    <div ref={ref} className={cn('relative inline-flex', className)}>
      <div onClick={() => setOpen(!open)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            'absolute top-full mt-1.5 z-50 min-w-[200px] rounded-xl p-1.5',
            'glass shadow-lg',
            'animate-fade-in-down',
            align === 'right' ? 'right-0' : 'left-0'
          )}
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      )}
    </div>
  )
}

interface DropdownItemProps {
  children: ReactNode
  icon?: ReactNode
  danger?: boolean
  onClick?: () => void
  className?: string
}

export function DropdownItem({ children, icon, danger, onClick, className }: DropdownItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-left',
        'transition-colors duration-150',
        danger
          ? 'text-danger hover:bg-danger/10'
          : 'text-text-secondary hover:bg-surface-2/80 hover:text-text',
        className
      )}
    >
      {icon && <span className="shrink-0 opacity-70">{icon}</span>}
      {children}
    </button>
  )
}

export function DropdownSeparator() {
  return <div className="my-1 h-px bg-border" />
}
