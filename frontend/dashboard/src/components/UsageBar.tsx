interface UsageBarProps {
  used: number
  limit: number
  label: string
  unit?: 'count' | 'bytes'
}

function formatBytes(n: number) {
  if (n >= 1e9) return `${(n / 1e9).toFixed(n % 1e9 === 0 ? 0 : 1)} GB`
  if (n >= 1e6) return `${Math.round(n / 1e6)} MB`
  if (n >= 1e3) return `${Math.round(n / 1e3)} KB`
  return `${n} B`
}

export default function UsageBar({ used, limit, label, unit = 'count' }: UsageBarProps) {
  const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0
  const barColor = pct > 90 ? 'bg-danger' : 'bg-text'
  const fmt = unit === 'bytes' ? formatBytes : (n: number) => n.toLocaleString()

  return (
    <div className="mb-4">
      <div className="mb-1.5 flex justify-between text-sm">
        <span className="text-text-secondary">{label}</span>
        <span className="tabular text-muted">
          {fmt(used)} / {fmt(limit)}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div
          className={`h-full origin-left rounded-full transition-transform duration-short ease-out ${barColor}`}
          style={{ transform: `scaleX(${pct / 100})` }}
        />
      </div>
    </div>
  )
}
