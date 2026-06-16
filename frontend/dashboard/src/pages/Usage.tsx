import { useEffect, useState } from 'react'
import { Download } from 'lucide-react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { UsageHistoryResponse, UsageSummary, UsageTimeseries } from '@shared/types'
import api from '../lib/api'
import UsageBar from '../components/UsageBar'
import { Button, Card, CardHeader, CardTitle, Skeleton } from '../components/ui'

export default function Usage() {
  const [summary, setSummary] = useState<UsageSummary | null>(null)
  const [history, setHistory] = useState<UsageHistoryResponse | null>(null)
  const [timeseries, setTimeseries] = useState<UsageTimeseries | null>(null)
  const [range, setRange] = useState<'7d' | '30d' | '90d'>('7d')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    void Promise.all([
      api.get<UsageSummary>('/usage/summary'),
      api.get<UsageHistoryResponse>('/usage/history'),
      api.get<UsageTimeseries>(`/usage/timeseries?range=${range}`),
    ]).then(([s, h, t]) => {
      setSummary(s.data)
      setHistory(h.data)
      setTimeseries(t.data)
      setLoading(false)
    })
  }, [range])

  const exportCsv = () => {
    if (!history) return
    const rows = [['Question', 'Tokens', 'Confidence', 'Date'], ...history.items.map((i) => [
      `"${i.question.replace(/"/g, '""')}"`, i.tokens_total, i.confidence_score ?? '', i.created_at ?? '',
    ])]
    const blob = new Blob([rows.map((r) => r.join(',')).join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'query-history.csv'
    a.click()
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Analytics</h1>
        <div className="flex gap-2">
          {(['7d', '30d', '90d'] as const).map((r) => (
            <Button key={r} variant={range === r ? 'primary' : 'ghost'} size="sm" onClick={() => setRange(r)}>{r}</Button>
          ))}
          <Button variant="secondary" size="sm" onClick={exportCsv}><Download size={14} /> Export</Button>
        </div>
      </div>

      {summary && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
          <Card className="p-4"><p className="text-xs text-muted">Plan</p><p className="text-xl font-bold capitalize">{summary.plan}</p></Card>
          <Card className="p-4"><p className="text-xs text-muted">Queries</p><p className="text-xl font-bold">{history?.total ?? 0}</p></Card>
          <Card className="p-4 col-span-2">
            <UsageBar label="Tokens" used={summary.tokens_used} limit={summary.tokens_limit} />
          </Card>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2 mb-8">
        <Card>
          <CardHeader><CardTitle>Token usage</CardTitle></CardHeader>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={timeseries?.tokens_by_day ?? []}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="var(--muted)" />
              <YAxis tick={{ fontSize: 10 }} stroke="var(--muted)" />
              <Tooltip />
              <Area type="monotone" dataKey="tokens" stroke="var(--primary)" fill="var(--primary-muted)" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
        <Card>
          <CardHeader><CardTitle>Queries per day</CardTitle></CardHeader>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={timeseries?.queries_by_day ?? []}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="var(--muted)" />
              <YAxis tick={{ fontSize: 10 }} stroke="var(--muted)" />
              <Tooltip />
              <Bar dataKey="queries" fill="var(--accent-blue)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card className="mb-8">
        <CardHeader><CardTitle>Confidence trend</CardTitle></CardHeader>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={timeseries?.confidence_by_day ?? []}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="var(--muted)" />
            <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} stroke="var(--muted)" />
            <Tooltip />
            <Line type="monotone" dataKey="avg_confidence" stroke="var(--accent-purple)" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <Card>
        <CardHeader><CardTitle>Query history</CardTitle></CardHeader>
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {history?.items.map((item) => (
            <div key={item.id} className="border-b border-border-subtle pb-3 last:border-0">
              <p className="text-sm font-medium">{item.question}</p>
              <p className="text-xs text-muted mt-1 line-clamp-2">{item.answer}</p>
              <div className="flex gap-3 mt-1 text-[10px] text-muted">
                <span>{item.tokens_total} tokens</span>
                {item.confidence_score != null && <span>{(item.confidence_score * 100).toFixed(0)}% confidence</span>}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
