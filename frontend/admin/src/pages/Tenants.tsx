import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { AdminTenant } from '@shared/types'
import adminApi from '../lib/adminApi'

export default function Tenants() {
  const [tenants, setTenants] = useState<AdminTenant[]>([])

  useEffect(() => {
    void adminApi.get<AdminTenant[]>('/admin/tenants').then((r) => setTenants(r.data)).catch(() => {})
  }, [])

  const toggleActive = async (tenantId: string, currentStatus: boolean) => {
    await adminApi.patch(`/admin/tenants/${tenantId}`, { is_active: !currentStatus })
    setTenants((prev) =>
      prev.map((t) => (t.id === tenantId ? { ...t, is_active: !currentStatus } : t))
    )
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h2>All Tenants</h2>
        <Link to="/usage" style={{ color: 'var(--primary)' }}>
          Global Usage →
        </Link>
      </div>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Plan</th>
            <th>Monthly tokens</th>
            <th>Storage</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {tenants.map((t) => (
            <tr key={t.id}>
              <td>{t.name}</td>
              <td>
                <span className={`badge ${t.plan}`}>{t.plan}</span>
              </td>
              <td>
                {t.monthly_tokens_used.toLocaleString()} / {t.monthly_token_limit.toLocaleString()}
              </td>
              <td>{(t.storage_used_bytes / 1024 / 1024).toFixed(1)} MB</td>
              <td>
                <button
                  className={`toggle ${t.is_active ? 'active' : 'inactive'}`}
                  onClick={() => void toggleActive(t.id, t.is_active)}
                >
                  {t.is_active ? 'Active' : 'Suspended'}
                </button>
              </td>
              <td>
                <Link to={`/tenants/${t.id}`} style={{ color: 'var(--primary)' }}>
                  View
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
