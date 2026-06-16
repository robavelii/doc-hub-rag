import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { QuerySource } from '@shared/types'
import { cn } from '../lib/cn'

interface SourcesPanelProps {
  sources: QuerySource[]
}

export default function SourcesPanel({ sources }: SourcesPanelProps) {
  const [open, setOpen] = useState(false)

  if (!sources.length) return null

  const unique = sources.reduce<QuerySource[]>((acc, s) => {
    if (!acc.find((x) => x.id === s.id)) acc.push(s)
    return acc
  }, [])

  return (
    <div className="mt-3 rounded-md border border-border bg-surface-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-3 py-2 text-sm font-medium text-text hover:bg-surface transition-colors"
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        Sources ({unique.length})
      </button>
      {open && (
        <div className="border-t border-border px-3 py-2 space-y-2">
          {unique.map((s, i) => (
            <div key={s.id} className="text-sm">
              <div className="flex items-baseline gap-2">
                <span className="shrink-0 rounded-sm bg-primary/15 px-1.5 py-0.5 text-xs font-medium text-primary">
                  [{i + 1}]
                </span>
                <span className="font-medium text-text truncate">{s.filename || 'source'}</span>
              </div>
              <p className="mt-1 text-muted leading-relaxed line-clamp-3">{s.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function SourcesToggle({
  count,
  active,
  onClick,
}: {
  count: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'text-xs font-medium px-2 py-1 rounded-sm transition-colors',
        active ? 'bg-primary/15 text-primary' : 'text-muted hover:text-text hover:bg-surface-2'
      )}
    >
      {count} {count === 1 ? 'source' : 'sources'}
    </button>
  )
}
