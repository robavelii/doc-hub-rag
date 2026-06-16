import { useState } from 'react'
import type { QuerySource } from '@shared/types'
import { cn } from '../lib/cn'

interface CitationPillProps {
  chunkId: string
  source?: QuerySource
  refNum?: number
}

export default function CitationPill({ chunkId, source, refNum }: CitationPillProps) {
  const [showPopover, setShowPopover] = useState(false)
  const label = refNum != null ? `[${refNum}]` : `[${source?.filename || 'source'}]`

  return (
    <span className="relative inline-block align-baseline mx-0.5">
      <button
        type="button"
        className={cn(
          'inline-flex items-center rounded-full px-1.5 py-0 text-xs font-medium',
          'bg-primary/15 text-primary hover:bg-primary/25 transition-colors cursor-help'
        )}
        onMouseEnter={() => setShowPopover(true)}
        onMouseLeave={() => setShowPopover(false)}
        onFocus={() => setShowPopover(true)}
        onBlur={() => setShowPopover(false)}
        aria-label={`Source citation ${refNum ?? chunkId}`}
      >
        {label}
      </button>
      {showPopover && source?.text && (
        <span
          role="tooltip"
          className={cn(
            'absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-10',
            'w-64 rounded-md border border-border bg-surface p-2 shadow-md text-xs text-muted',
            'pointer-events-none'
          )}
        >
          <span className="block font-medium text-text mb-1">{source.filename || 'source'}</span>
          {source.text.slice(0, 300)}
          {source.text.length > 300 ? '…' : ''}
        </span>
      )}
    </span>
  )
}
