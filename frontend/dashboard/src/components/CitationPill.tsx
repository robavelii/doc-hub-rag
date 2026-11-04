import { useState } from 'react'
import type { QuerySource } from '@shared/types'

interface CitationPillProps {
  chunkId: string
  source?: QuerySource
  refNum?: number
}

export default function CitationPill({ chunkId, source, refNum }: CitationPillProps) {
  const [showPopover, setShowPopover] = useState(false)
  const label = refNum != null ? String(refNum) : source?.filename || 'source'

  return (
    <span className="relative mx-0.5 inline-block align-[0.12em]">
      <button
        type="button"
        className="inline-flex h-[18px] min-w-[18px] cursor-help items-center justify-center rounded-md bg-accent-soft px-1 text-[11px] font-semibold leading-none text-accent transition-colors duration-micro hover:bg-accent hover:text-primary-fg"
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
          className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 w-72 -translate-x-1/2 rounded-xl border border-border bg-surface p-3 text-left text-xs font-normal leading-relaxed text-text-secondary shadow-lg"
        >
          <span className="mb-1 block font-medium text-text">{source.filename || 'source'}</span>
          {source.text.slice(0, 300)}
          {source.text.length > 300 ? '…' : ''}
        </span>
      )}
    </span>
  )
}
