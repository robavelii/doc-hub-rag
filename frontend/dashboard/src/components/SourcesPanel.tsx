import { useState } from 'react'
import { FileText } from 'lucide-react'
import type { QuerySource } from '@shared/types'
import { buildSourceIndexMap } from '../lib/markdown'
import { cn } from '../lib/cn'

interface SourcesPanelProps {
  sources: QuerySource[]
}

export default function SourcesPanel({ sources }: SourcesPanelProps) {
  const [openId, setOpenId] = useState<string | null>(null)

  if (!sources.length) return null

  // Numbered with the same map as the in-text citations, so chip 3 is always [3]
  const indexMap = buildSourceIndexMap(sources)
  const unique = sources.filter((s, i) => sources.findIndex((x) => x.id === s.id) === i)
  const open = unique.find((s) => s.id === openId)

  return (
    <div className="mt-3">
      <h4 className="sr-only">Sources</h4>
      <ul className="flex flex-wrap gap-1.5">
        {unique.map((s) => {
          const active = s.id === openId
          return (
            <li key={s.id}>
              <button
                type="button"
                aria-expanded={active}
                onClick={() => setOpenId(active ? null : s.id)}
                className={cn(
                  'inline-flex h-7 max-w-[18rem] items-center gap-1.5 rounded-lg border px-2 text-xs transition-colors duration-micro',
                  active
                    ? 'border-accent/40 bg-accent-soft text-text'
                    : 'border-border bg-surface text-text-secondary hover:border-border-strong hover:text-text'
                )}
              >
                <span className="tabular font-semibold text-accent">{indexMap.get(s.id)}</span>
                <span className="truncate">{s.filename || 'source'}</span>
              </button>
            </li>
          )
        })}
      </ul>
      {open && (
        <figure className="mt-2 rounded-xl border border-border bg-surface p-3.5 shadow-sm">
          <figcaption className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-text">
            <FileText size={13} className="text-muted" aria-hidden="true" />
            {open.filename || 'source'}
          </figcaption>
          <blockquote className="text-sm leading-relaxed text-text-secondary">{open.text}</blockquote>
        </figure>
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
      aria-pressed={active}
      className={cn(
        'rounded-md px-2 py-1 text-xs font-medium transition-colors duration-micro',
        active ? 'bg-accent-soft text-text' : 'text-muted hover:bg-primary-muted hover:text-text'
      )}
    >
      {count} {count === 1 ? 'source' : 'sources'}
    </button>
  )
}
