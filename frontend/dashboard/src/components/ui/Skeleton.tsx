import { cn } from '../../lib/cn'

interface SkeletonProps {
  className?: string
  variant?: 'text' | 'circular' | 'rectangular'
  width?: string | number
  height?: string | number
}

export function Skeleton({ className, variant = 'text', width, height }: SkeletonProps) {
  return (
    <div
      className={cn(
        'bg-surface-2 animate-shimmer',
        variant === 'text' && 'h-4 rounded-md',
        variant === 'circular' && 'rounded-full',
        variant === 'rectangular' && 'rounded-lg',
        className
      )}
      style={{
        width: width ?? (variant === 'circular' ? 40 : '100%'),
        height: height ?? (variant === 'circular' ? 40 : variant === 'rectangular' ? 120 : undefined),
        backgroundImage: 'linear-gradient(90deg, transparent 0%, var(--glass-highlight) 50%, transparent 100%)',
        backgroundSize: '200% 100%',
      }}
    />
  )
}

/** Preset: skeleton for a card with title + 3 lines */
export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-xl border border-border bg-surface p-5 space-y-3', className)}>
      <Skeleton width="40%" height={20} />
      <Skeleton width="100%" />
      <Skeleton width="85%" />
      <Skeleton width="65%" />
    </div>
  )
}

/** Preset: skeleton for a table row */
export function SkeletonRow({ cols = 4, className }: { cols?: number; className?: string }) {
  return (
    <div className={cn('flex gap-4 py-3', className)}>
      {Array.from({ length: cols }).map((_, i) => (
        <Skeleton key={i} width={`${Math.random() * 30 + 20}%`} height={16} />
      ))}
    </div>
  )
}
