import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { AdminTenant, GlobalUsageStats } from '@shared/types'
import api from '../../lib/api'
import { Card, CardHeader, CardTitle, Skeleton } from '../../components/ui'

const PLAN_COLORS = ['#6b7d96', '#1dd89b', '#60a5fa']

export default function AdminGlobalUsage() {
  const [stats, setStats] = useState<GlobalUsageStats | null>(null)
  const [tenants, setTenants] = useState<AdminTenant[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void Promise.all([
      api.get<GlobalUsageStats>('/admin/usage/global'),
      api.get<AdminTenant[]>('/admin/tenants'),
    ]).then(([s, t]) => {
      setStats(s.data)
      setTenants(t.data)
      setLoading(false)
    })
  }, [])

  if (loading) return <Skeleton className="h-64" />

  const planDist = ['free', 'starter', 'pro'].map((plan) => ({
    name: plan,
    value: tenants.filter((t) => t.plan === plan).length,
  })).filter((p) => p.value > 0)

  const tokenByTenant = tenants.slice(0, 8).map((t) => ({
    name: t.name.slice(0, 12),
    tokens: t.monthly_tokens_used,
  }))

  const active = tenants.filter((t) => t.is_active).length
  const suspended = tenants.length - active

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Admin — Global Usage</h1>
      <div className="grid gap-4 sm:grid-cols-4 mb-8">
        <Card className="p-4"><p className="text-xs text-muted">Total tokens</p><p className="text-2xl font-bold">{(stats?.total_tokens_this_month ?? 0).toLocaleString()}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted">Tenants</p><p className="text-2xl font-bold">{stats?.total_tenants ?? 0}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted">Active</p><p className="text-2xl font-bold text-success">{active}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted">Suspended</p><p className="text-2xl font-bold text-danger">{suspended}</p></Card>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Tokens by tenant</CardTitle></CardHeader>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={tokenByTenant}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="tokens" fill="var(--primary)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card>
          <CardHeader><CardTitle>Plan distribution</CardTitle></CardHeader>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={planDist} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                {planDist.map((_, i) => <Cell key={i} fill={PLAN_COLORS[i % PLAN_COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  )
}
