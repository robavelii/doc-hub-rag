import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { QueryResultMetrics } from '@shared/types'
import { Badge } from './ui'

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
    <div className="mt-3 rounded-md border border-border bg-surface-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-sm"
      >
        <span className="flex items-center gap-2 text-muted">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span>Metrics</span>
          <Badge variant={conf.variant}>{conf.pct}%</Badge>
        </span>
        <span className="flex items-center gap-1.5">
          {latency && <Badge>{latency}</Badge>}
          {from_cache && <Badge variant="info">Cached</Badge>}
        </span>
      </button>

      {open && (
        <div className="border-t border-border px-3 py-3 space-y-3">
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted">Confidence</span>
              <span className="font-medium">{conf.pct}% — {conf.label}</span>
            </div>
            <div className="h-1.5 rounded-full bg-border overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${conf.pct}%` }}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Badge>{sourceCount} {sourceCount === 1 ? 'source' : 'sources'}</Badge>
            {tokens_total != null && tokens_total > 0 && (
              <Badge>{tokens_total.toLocaleString()} tokens</Badge>
            )}
            {modelLabel && <Badge variant="info">{modelLabel}</Badge>}
          </div>
        </div>
      )}
    </div>
  )
}
