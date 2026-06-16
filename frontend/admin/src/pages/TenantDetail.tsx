import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import type { AdminTenant } from '@shared/types'
import adminApi from '../lib/adminApi'

export default function TenantDetail() {
  const { id } = useParams<{ id: string }>()
  const [tenant, setTenant] = useState<AdminTenant | null>(null)

  useEffect(() => {
    if (id) {
      void adminApi.get<AdminTenant>(`/admin/tenants/${id}`).then((r) => setTenant(r.data))
    }
  }, [id])

  if (!tenant) return <p>Loading...</p>

  return (
    <div>
      <Link to="/" style={{ color: 'var(--primary)' }}>
        ← Back
      </Link>
      <div className="card" style={{ marginTop: '1rem' }}>
        <h2>{tenant.name}</h2>
        <p>Plan: {tenant.plan}</p>
        <p>Status: {tenant.is_active ? 'Active' : 'Suspended'}</p>
        <p>
          Tokens: {tenant.monthly_tokens_used} / {tenant.monthly_token_limit}
        </p>
        <p>Storage: {(tenant.storage_used_bytes / 1024 / 1024).toFixed(1)} MB</p>
      </div>
    </div>
  )
}
