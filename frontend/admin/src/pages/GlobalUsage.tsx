import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { GlobalUsageStats } from '@shared/types'
import adminApi from '../lib/adminApi'
import UsageChart from '../components/UsageChart'

export default function GlobalUsage() {
  const [stats, setStats] = useState<GlobalUsageStats | null>(null)

  useEffect(() => {
    void adminApi.get<GlobalUsageStats>('/admin/usage/global').then((r) => setStats(r.data))
  }, [])

  const chartData = [
    { month: 'Jan', tokens: 120000 },
    { month: 'Feb', tokens: 180000 },
    { month: 'Mar', tokens: stats?.total_tokens_this_month ?? 0 },
  ]

  return (
    <div>
      <Link to="/" style={{ color: 'var(--primary)' }}>
        ← Back
      </Link>
      <div className="card" style={{ marginTop: '1rem' }}>
        <h2>Global Usage</h2>
        {stats && (
          <>
            <p>Total tokens this month: {stats.total_tokens_this_month.toLocaleString()}</p>
            <p>Total tenants: {stats.total_tenants}</p>
          </>
        )}
        <div style={{ marginTop: '2rem' }}>
          <UsageChart data={chartData} />
        </div>
      </div>
    </div>
  )
}
