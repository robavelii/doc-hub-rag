interface UsageBarProps {
  used: number
  limit: number
  label: string
}

export default function UsageBar({ used, limit, label }: UsageBarProps) {
  const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0
  const barColor = pct > 90 ? 'bg-danger' : 'bg-primary'

  return (
    <div className="mb-4">
      <div className="flex justify-between text-sm mb-1">
        <span>{label}</span>
        <span className="text-muted">
          {used.toLocaleString()} / {limit.toLocaleString()}
        </span>
      </div>
      <div className="bg-border rounded-md h-2 overflow-hidden">
        <div
          className={`h-full rounded-md transition-all duration-300 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
