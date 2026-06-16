import { cn } from '../../lib/cn'

interface AvatarProps {
  name?: string
  src?: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizes = {
  sm: 'h-7 w-7 text-xs',
  md: 'h-9 w-9 text-sm',
  lg: 'h-11 w-11 text-base',
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) {
    const first = parts[0] || ''
    const last = parts[parts.length - 1] || ''
    if (first.length > 0 && last.length > 0) {
      return (first.charAt(0) + last.charAt(0)).toUpperCase()
    }
  }
  return name.slice(0, 2).toUpperCase()
}

function hashColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue}, 55%, 45%)`
}

export function Avatar({ name = '', src, size = 'md', className }: AvatarProps) {
  if (src) {
    return (
      <img
        src={src}
        alt={name}
        className={cn('rounded-full object-cover', sizes[size], className)}
      />
    )
  }

  const initials = getInitials(name || '?')
  const bg = hashColor(name)

  return (
    <div
      className={cn(
        'inline-flex items-center justify-center rounded-full font-medium text-white shrink-0',
        sizes[size],
        className
      )}
      style={{ backgroundColor: bg }}
      title={name}
    >
      {initials}
    </div>
  )
}
