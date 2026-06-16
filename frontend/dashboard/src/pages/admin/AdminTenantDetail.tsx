import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { AdminTenant } from '@shared/types'
import api from '../../lib/api'
import { Card, Skeleton } from '../../components/ui'

export default function AdminTenantDetail() {
  const { id } = useParams<{ id: string }>()
  const [tenant, setTenant] = useState<AdminTenant | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    void api
      .get<AdminTenant>(`/admin/tenants/${id}`)
      .then(({ data }) => setTenant(data))
      .catch(() => setError('Failed to load tenant'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (error || !tenant) {
    return <p className="text-danger">{error ?? 'Tenant not found'}</p>
  }

  return (
    <div>
      <Link to="/admin/tenants" className="text-sm text-brand hover:underline">
        ← Back to tenants
      </Link>
      <h1 className="text-2xl font-bold mt-4 mb-6">{tenant.name}</h1>
      <Card className="p-6 space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs text-muted">Plan</p>
            <p className="font-medium capitalize">{tenant.plan}</p>
          </div>
          <div>
            <p className="text-xs text-muted">Status</p>
            <p className="font-medium">{tenant.is_active ? 'Active' : 'Suspended'}</p>
          </div>
          <div>
            <p className="text-xs text-muted">Tokens this month</p>
            <p className="font-medium">
              {tenant.monthly_tokens_used.toLocaleString()} / {tenant.monthly_token_limit.toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted">Storage</p>
            <p className="font-medium">{(tenant.storage_used_bytes / 1024 / 1024).toFixed(1)} MB</p>
          </div>
        </div>
        {tenant.widget_config && (
          <div>
            <p className="text-xs text-muted mb-2">Widget config</p>
            <pre className="text-xs bg-bg rounded-lg p-3 overflow-auto border border-border">
              {JSON.stringify(tenant.widget_config, null, 2)}
            </pre>
          </div>
        )}
      </Card>
    </div>
  )
}
