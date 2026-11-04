import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import type { QueryResultMetrics } from '@shared/types'
import { Badge } from './ui'
import { cn } from '../lib/cn'

interface QueryMetricsProps {
  metrics: QueryResultMetrics
}

function confidenceMeta(score: number) {
  const pct = Math.round(score * 100)
  if (score >= 0.7) return { pct, label: 'High confidence', variant: 'success' as const }
  if (score >= 0.5) return { pct, label: 'Good match', variant: 'success' as const }
  if (score >= 0.35) return { pct, label: 'Partial match', variant: 'warning' as const }
  if (score > 0) return { pct, label: 'Low confidence', variant: 'warning' as const }
  return { pct: 0, label: 'No match', variant: 'default' as const }
}

function formatLatency(ms?: number | null) {
  if (ms == null) return null
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function uniqueSourceCount(sources: QueryResultMetrics['sources']) {
  const names = new Set(sources.map((s) => s.filename || s.doc_id || s.id).filter(Boolean))
  return names.size || sources.length
}

function formatModelLabel(provider?: string | null, model?: string | null) {
  if (!model) return null
  if (provider && provider !== 'fallback') return `${provider}/${model}`
  return model
}

export default function QueryMetrics({ metrics }: QueryMetricsProps) {
  const [open, setOpen] = useState(false)
  const { confidence, sources, tokens_total, latency_ms, from_cache, provider, model } = metrics
  const conf = confidenceMeta(confidence)
  const sourceCount = uniqueSourceCount(sources)
  const latency = formatLatency(latency_ms)
  const modelLabel = formatModelLabel(provider, model)

  return (
    <div className="mt-1">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="inline-flex h-7 items-center gap-2 rounded-lg px-1.5 text-xs text-muted transition-colors duration-micro hover:bg-primary-muted hover:text-text"
      >
        <span>Metrics</span>
        <Badge variant={conf.variant}>{conf.pct}%</Badge>
        {latency && <span className="tabular">{latency}</span>}
        {from_cache && <Badge variant="info">Cached</Badge>}
        <ChevronDown size={13} className={cn('transition-transform duration-micro', open && 'rotate-180')} aria-hidden="true" />
      </button>

      {open && (
        <div className="mt-1.5 max-w-md space-y-3 rounded-xl border border-border bg-surface p-3">
          <div>
            <div className="mb-1 flex justify-between text-xs">
              <span className="text-muted">Confidence</span>
              <span className="font-medium text-text">
                {conf.pct}%, {conf.label}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
              <div className="h-full origin-left rounded-full bg-text" style={{ transform: `scaleX(${conf.pct / 100})` }} />
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Badge>
              {sourceCount} {sourceCount === 1 ? 'source' : 'sources'}
            </Badge>
            {tokens_total != null && tokens_total > 0 && <Badge>{tokens_total.toLocaleString()} tokens</Badge>}
            {modelLabel && <Badge variant="info">{modelLabel}</Badge>}
          </div>
        </div>
      )}
    </div>
  )
}
