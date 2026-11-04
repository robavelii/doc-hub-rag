import { useState, useRef, useEffect, type ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface TooltipProps {
  content: string
  children: ReactNode
  side?: 'top' | 'bottom' | 'left' | 'right'
  className?: string
}

const positionStyles = {
  top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
  bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
  left: 'right-full top-1/2 -translate-y-1/2 mr-2',
  right: 'left-full top-1/2 -translate-y-1/2 ml-2',
}

export function Tooltip({ content, children, side = 'top', className }: TooltipProps) {
  const [show, setShow] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  const handleEnter = () => {
    timerRef.current = setTimeout(() => setShow(true), 400)
  }
  const handleLeave = () => {
    clearTimeout(timerRef.current)
    setShow(false)
  }

  useEffect(() => {
    return () => clearTimeout(timerRef.current)
  }, [])

  return (
    <div
      className={cn('relative inline-flex', className)}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      onFocus={handleEnter}
      onBlur={handleLeave}
    >
      {children}
      {show && (
        <div
          className={cn(
            'pointer-events-none absolute z-50 whitespace-nowrap rounded-md bg-text px-2 py-1 text-xs font-medium text-bg shadow-md',
            positionStyles[side]
          )}
          role="tooltip"
        >
          {content}
        </div>
      )}
    </div>
  )
}
