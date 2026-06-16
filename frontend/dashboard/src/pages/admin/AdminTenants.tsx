import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { AdminTenant } from '@shared/types'
import api from '../../lib/api'
import { Badge, Button, Card, Input, Skeleton } from '../../components/ui'

export default function AdminTenants() {
  const [tenants, setTenants] = useState<AdminTenant[]>([])
  const [search, setSearch] = useState('')
  const [planFilter, setPlanFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState('')

  const load = () => void api.get<AdminTenant[]>('/admin/tenants').then(({ data }) => { setTenants(data); setLoading(false) })
  useEffect(() => { load() }, [])

  const filtered = tenants.filter((t) => {
    if (search && !t.name.toLowerCase().includes(search.toLowerCase())) return false
    if (planFilter && t.plan !== planFilter) return false
    return true
  })

  const toggleActive = async (id: string, is_active: boolean) => {
    await api.patch(`/admin/tenants/${id}`, { is_active: !is_active })
    load()
  }

  const create = async () => {
    await api.post('/admin/tenants', { name: newName })
    setNewName('')
    load()
  }

  if (loading) return <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div>

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Admin — Tenants</h1>
      <div className="flex gap-2 mb-4 flex-wrap">
        <Input placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)} className="w-48" />
        <select value={planFilter} onChange={(e) => setPlanFilter(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2 text-sm">
          <option value="">All plans</option>
          <option value="free">Free</option>
          <option value="starter">Starter</option>
          <option value="pro">Pro</option>
        </select>
        <Input placeholder="New tenant name" value={newName} onChange={(e) => setNewName(e.target.value)} className="w-48" />
        <Button onClick={() => void create()}>Create</Button>
      </div>
      <Card>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted border-b border-border">
              <th className="py-2 px-4">Name</th>
              <th className="py-2 px-4">Plan</th>
              <th className="py-2 px-4">Tokens</th>
              <th className="py-2 px-4">Status</th>
              <th className="py-2 px-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr key={t.id} className="border-b border-border-subtle">
                <td className="py-3 px-4"><Link to={`/admin/tenants/${t.id}`} className="font-medium hover:text-primary">{t.name}</Link></td>
                <td className="py-3 px-4"><Badge variant="primary">{t.plan}</Badge></td>
                <td className="py-3 px-4 text-muted">{t.monthly_tokens_used.toLocaleString()} / {t.monthly_token_limit.toLocaleString()}</td>
                <td className="py-3 px-4"><Badge variant={t.is_active ? 'success' : 'danger'}>{t.is_active ? 'Active' : 'Suspended'}</Badge></td>
                <td className="py-3 px-4">
                  <Button size="sm" variant="secondary" onClick={() => void toggleActive(t.id, t.is_active)}>
                    {t.is_active ? 'Suspend' : 'Activate'}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
