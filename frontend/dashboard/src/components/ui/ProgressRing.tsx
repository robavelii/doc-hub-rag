import { cn } from '../../lib/cn'

interface ProgressRingProps {
  value: number
  max?: number
  size?: number
  strokeWidth?: number
  className?: string
  label?: string
  color?: string
}

export function ProgressRing({
  value,
  max = 100,
  size = 48,
  strokeWidth = 4,
  className,
  label,
  color,
}: ProgressRingProps) {
  const pct = Math.min(Math.max(value / max, 0), 1)
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - pct)

  const getColor = () => {
    if (color) return color
    if (pct >= 0.9) return 'var(--danger)'
    if (pct >= 0.7) return 'var(--warning)'
    return 'var(--primary)'
  }

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--border)"
          strokeWidth={strokeWidth}
        />
        {/* Progress ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={getColor()}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 600ms ease-out, stroke 300ms ease' }}
        />
      </svg>
      {label && (
        <span className="absolute text-xs font-semibold text-text">
          {label}
        </span>
      )}
    </div>
  )
}
