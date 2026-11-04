import { useEffect, useState } from 'react'
import type { ApiKeyItem, BillingSubscription, CollectionItem, GroupItem, TeamMember } from '@shared/types'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { useSearchParams } from 'react-router-dom'
import { Button, Card, Input, Skeleton, useToast } from '../components/ui'
import UsageBar from '../components/UsageBar'
import { cn } from '../lib/cn'

type Tab = 'profile' | 'team' | 'access' | 'sso' | 'compliance' | 'keys' | 'billing' | 'danger'

const TABS: { id: Tab; label: string }[] = [
  { id: 'profile', label: 'Profile' },
  { id: 'team', label: 'Team' },
  { id: 'access', label: 'Access' },
  { id: 'sso', label: 'SSO' },
  { id: 'compliance', label: 'Compliance' },
  { id: 'keys', label: 'API Keys' },
  { id: 'billing', label: 'Billing' },
  { id: 'danger', label: 'Danger Zone' },
]

export default function Settings() {
  const [searchParams] = useSearchParams()
  const initialTab = (searchParams.get('billing') ? 'billing' : searchParams.get('tab')) as Tab | null
  const [tab, setTab] = useState<Tab>(initialTab && TABS.some((t) => t.id === initialTab) ? initialTab : 'profile')
  const { user, tenant } = useAuthStore()
  const { toast } = useToast()
  const visibleTabs = TABS.filter((t) => !['access', 'sso', 'compliance'].includes(t.id) || user?.role !== 'member')

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-6">Settings</h1>
      <div className="flex gap-1 mb-6 border-b border-border overflow-x-auto">
        {visibleTabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition whitespace-nowrap',
              tab === t.id ? 'border-primary text-primary' : 'border-transparent text-muted hover:text-text'
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'profile' && <ProfileTab user={user} toast={toast} />}
      {tab === 'team' && <TeamTab toast={toast} />}
      {tab === 'access' && <AccessTab toast={toast} />}
      {tab === 'sso' && <SsoTab toast={toast} />}
      {tab === 'compliance' && <ComplianceTab toast={toast} />}
      {tab === 'keys' && <ApiKeysTab toast={toast} />}
      {tab === 'billing' && <BillingTab toast={toast} />}
      {tab === 'danger' && <DangerTab tenant={tenant} toast={toast} />}
    </div>
  )
}

function ProfileTab({ user, toast }: { user: ReturnType<typeof useAuthStore.getState>['user']; toast: ReturnType<typeof useToast>['toast'] }) {
  const [displayName, setDisplayName] = useState(user?.display_name ?? '')
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')

  const saveProfile = async () => {
    await api.patch('/auth/profile', { display_name: displayName })
    toast('success', 'Profile updated')
  }

  const changePassword = async () => {
    await api.post('/auth/change-password', { current_password: currentPw, new_password: newPw })
    setCurrentPw(''); setNewPw('')
    toast('success', 'Password changed')
  }

  return (
    <div className="grid gap-6 max-w-lg">
      <Card className="p-6 space-y-4">
        <h3 className="font-semibold">Account</h3>
        <div><label className="text-xs text-muted">Email</label><Input value={user?.email ?? ''} disabled /></div>
        <div><label className="text-xs text-muted">Role</label><Input value={user?.role ?? ''} disabled /></div>
        <div><label className="text-xs text-muted">Display name</label><Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} /></div>
        <Button onClick={() => void saveProfile()}>Save profile</Button>
      </Card>
      <Card className="p-6 space-y-4">
        <h3 className="font-semibold">Change password</h3>
        <Input type="password" placeholder="Current password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} />
        <Input type="password" placeholder="New password" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
        <Button onClick={() => void changePassword()}>Update password</Button>
      </Card>
    </div>
  )
}

function TeamTab({ toast }: { toast: ReturnType<typeof useToast>['toast'] }) {
  const [members, setMembers] = useState<TeamMember[]>([])
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteToken, setInviteToken] = useState('')

  const load = () => void api.get<TeamMember[]>('/auth/team').then(({ data }) => setMembers(data))
  useEffect(() => { load() }, [])

  const invite = async () => {
    const { data } = await api.post<{ invite_token: string }>('/auth/invite', { email: inviteEmail })
    setInviteToken(data.invite_token)
    toast('success', 'Invite created', 'Share the token with your teammate')
  }

  const remove = async (id: string) => {
    await api.delete(`/auth/team/${id}`)
    load()
    toast('success', 'Member removed')
  }

  return (
    <Card className="p-6 max-w-2xl">
      <h3 className="font-semibold mb-4">Team members</h3>
      <div className="space-y-2 mb-6">
        {members.map((m) => (
          <div key={m.id} className="flex items-center justify-between py-2 border-b border-border-subtle">
            <div><p className="text-sm font-medium">{m.email}</p><p className="text-xs text-muted capitalize">{m.role}</p></div>
            {m.role !== 'owner' && <Button variant="danger" size="sm" onClick={() => void remove(m.id)}>Remove</Button>}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <Input placeholder="email@company.com" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} />
        <Button onClick={() => void invite()}>Invite</Button>
      </div>
      {inviteToken && <p className="mt-2 text-xs text-muted">Token: <code className="font-mono text-text">{inviteToken}</code></p>}
    </Card>
  )
}

function errorDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown; error?: unknown } } })?.response?.data
  const value = detail?.detail ?? detail?.error
  return typeof value === 'string' ? value : fallback
}

function AccessTab({ toast }: { toast: ReturnType<typeof useToast>['toast'] }) {
  const [collections, setCollections] = useState<CollectionItem[]>([])
  const [groups, setGroups] = useState<GroupItem[]>([])
  const [newCollection, setNewCollection] = useState('')
  const [newGroup, setNewGroup] = useState('')
  const [memberEmail, setMemberEmail] = useState<Record<string, string>>({})

  const load = () => {
    void api.get<CollectionItem[]>('/collections').then(({ data }) => setCollections(data))
    void api.get<GroupItem[]>('/groups').then(({ data }) => setGroups(data)).catch(() => setGroups([]))
  }
  useEffect(() => { load() }, [])

  const run = async (action: () => Promise<unknown>, success: string) => {
    try {
      await action()
      toast('success', success)
      load()
    } catch (err) {
      toast('error', errorDetail(err, 'That did not work'))
    }
  }

  const toggleGroup = (c: CollectionItem, groupId: string) => {
    const current = new Set(c.group_ids ?? [])
    if (current.has(groupId)) current.delete(groupId)
    else current.add(groupId)
    void run(() => api.patch(`/collections/${c.id}`, { group_ids: [...current] }), 'Access updated')
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <Card className="p-6">
        <h3 className="font-semibold mb-1">Collections</h3>
        <p className="text-xs text-muted mb-4">
          Documents outside a collection are in General and visible to everyone. Restricted collections are visible
          only to owners, admins and the groups you tick.
        </p>
        <div className="flex gap-2 mb-4">
          <Input id="new-collection" placeholder="e.g. HR policies" value={newCollection} onChange={(e) => setNewCollection(e.target.value)} />
          <Button onClick={() => void run(async () => { await api.post('/collections', { name: newCollection, visibility: 'restricted' }); setNewCollection('') }, 'Collection created')} disabled={!newCollection.trim()}>
            Create
          </Button>
        </div>
        {collections.map((c) => (
          <div key={c.id} className="py-3 border-b border-border-subtle">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div>
                <p className="text-sm font-medium">{c.name}</p>
                <p className="text-xs text-muted">{c.document_count} document(s)</p>
              </div>
              <div className="flex items-center gap-2">
                <select
                  aria-label={`Visibility of ${c.name}`}
                  value={c.visibility}
                  onChange={(e) => void run(() => api.patch(`/collections/${c.id}`, { visibility: e.target.value }), 'Visibility updated')}
                  className="rounded-lg border border-border bg-surface px-2 py-1 text-sm"
                >
                  <option value="tenant">Everyone</option>
                  <option value="restricted">Selected groups</option>
                </select>
                <Button variant="danger" size="sm" onClick={() => void run(() => api.delete(`/collections/${c.id}`), 'Collection deleted')}>
                  Delete
                </Button>
              </div>
            </div>
            {c.visibility === 'restricted' && (
              <div className="flex flex-wrap gap-3 mt-2">
                {groups.length === 0 && <p className="text-xs text-muted">Create a group below to grant access.</p>}
                {groups.map((g) => (
                  <label key={g.id} className="flex items-center gap-1 text-xs">
                    <input type="checkbox" checked={(c.group_ids ?? []).includes(g.id)} onChange={() => toggleGroup(c, g.id)} />
                    {g.name}
                  </label>
                ))}
              </div>
            )}
          </div>
        ))}
      </Card>

      <Card className="p-6">
        <h3 className="font-semibold mb-4">Groups</h3>
        <div className="flex gap-2 mb-4">
          <Input id="new-group" placeholder="e.g. HR team" value={newGroup} onChange={(e) => setNewGroup(e.target.value)} />
          <Button onClick={() => void run(async () => { await api.post('/groups', { name: newGroup }); setNewGroup('') }, 'Group created')} disabled={!newGroup.trim()}>
            Create
          </Button>
        </div>
        {groups.map((g) => (
          <div key={g.id} className="py-3 border-b border-border-subtle">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">
                {g.name} {g.source === 'scim' && <span className="text-xs text-muted">· synced from your identity provider</span>}
              </p>
              {g.source !== 'scim' && (
                <Button variant="danger" size="sm" onClick={() => void run(() => api.delete(`/groups/${g.id}`), 'Group deleted')}>Delete</Button>
              )}
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {g.members.map((m) => (
                <span key={m.id} className="text-xs rounded-full border border-border px-2 py-0.5">
                  {m.email}
                  {g.source !== 'scim' && (
                    <button className="ml-1 text-muted" aria-label={`Remove ${m.email}`} onClick={() => void run(() => api.delete(`/groups/${g.id}/members/${m.id}`), 'Member removed')}>×</button>
                  )}
                </span>
              ))}
            </div>
            {g.source !== 'scim' && (
              <div className="flex gap-2 mt-2">
                <Input id={`member-${g.id}`} placeholder="teammate@company.com" value={memberEmail[g.id] ?? ''} onChange={(e) => setMemberEmail({ ...memberEmail, [g.id]: e.target.value })} />
                <Button size="sm" onClick={() => void run(async () => { await api.post(`/groups/${g.id}/members`, { email: memberEmail[g.id] }); setMemberEmail({ ...memberEmail, [g.id]: '' }) }, 'Member added')}>Add</Button>
              </div>
            )}
          </div>
        ))}
      </Card>
    </div>
  )
}

interface SsoConfig {
  available: boolean
  domains: string[]
  enforced: boolean
  callback_url: string
  connections: { name: string; type: string }[]
  directory: { type: string; scim_endpoint: string | null } | null
}

function SsoTab({ toast }: { toast: ReturnType<typeof useToast>['toast'] }) {
  const [config, setConfig] = useState<SsoConfig | null>(null)
  const [domains, setDomains] = useState('')
  const [enforced, setEnforced] = useState(false)
  const [metadataUrl, setMetadataUrl] = useState('')
  const [directoryType, setDirectoryType] = useState('okta-scim-v2')
  const [scim, setScim] = useState<{ scim_endpoint: string; scim_token: string } | null>(null)

  const load = () =>
    void api.get<SsoConfig>('/sso/config').then(({ data }) => {
      setConfig(data)
      setDomains(data.domains.join(', '))
      setEnforced(data.enforced)
    }).catch((err) => toast('error', errorDetail(err, 'Could not load SSO settings')))
  useEffect(() => { load() }, [])

  const run = async (action: () => Promise<unknown>, success: string) => {
    try {
      await action()
      toast('success', success)
      load()
    } catch (err) {
      toast('error', errorDetail(err, 'That did not work'))
    }
  }

  if (!config) return <Skeleton className="h-40 w-full max-w-2xl" />
  if (!config.available) {
    return <Card className="p-6 max-w-2xl"><p className="text-sm text-muted">Single sign-on is not enabled on this server.</p></Card>
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Card className="p-6 space-y-3">
        <h3 className="font-semibold">1. Identity provider</h3>
        <p className="text-xs text-muted">
          Create a SAML app in Okta, Entra ID or Google Workspace with this ACS / redirect URL, then paste its metadata URL.
        </p>
        <pre className="text-xs bg-bg border border-border rounded p-2 overflow-x-auto">{config.callback_url}</pre>
        {config.connections.length > 0 ? (
          <div className="flex items-center justify-between">
            <p className="text-sm">Connected: {config.connections.map((c) => `${c.name} (${c.type.toUpperCase()})`).join(', ')}</p>
            <Button variant="danger" size="sm" onClick={() => void run(() => api.delete('/sso/connection'), 'Connection removed')}>Remove</Button>
          </div>
        ) : (
          <div className="flex gap-2">
            <Input id="sso-metadata" placeholder="https://idp.example.com/app/metadata" value={metadataUrl} onChange={(e) => setMetadataUrl(e.target.value)} />
            <Button onClick={() => void run(() => api.post('/sso/connection', { metadata_url: metadataUrl }), 'Connected')} disabled={!metadataUrl.trim()}>Connect</Button>
          </div>
        )}
      </Card>

      <Card className="p-6 space-y-3">
        <h3 className="font-semibold">2. Email domains</h3>
        <p className="text-xs text-muted">People with these email domains are sent to your identity provider when they sign in.</p>
        <Input id="sso-domains" placeholder="company.com, company.co.uk" value={domains} onChange={(e) => setDomains(e.target.value)} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={enforced} onChange={(e) => setEnforced(e.target.checked)} />
          Require SSO for everyone except owners
        </label>
        <Button
          onClick={() => void run(() => api.put('/sso/domains', { domains: domains.split(',').map((d) => d.trim()).filter(Boolean), enforced }), 'Domains saved')}
        >
          Save
        </Button>
      </Card>

      <Card className="p-6 space-y-3">
        <h3 className="font-semibold">3. User provisioning (SCIM)</h3>
        {config.directory ? (
          <p className="text-sm">Connected ({config.directory.type}). Users and groups sync automatically; removed users lose access immediately.</p>
        ) : scim ? (
          <div className="space-y-2 text-sm">
            <p>Paste these into your identity provider’s SCIM settings. The token is shown once.</p>
            <pre className="text-xs bg-bg border border-border rounded p-2 overflow-x-auto">{scim.scim_endpoint}</pre>
            <pre className="text-xs bg-bg border border-border rounded p-2 overflow-x-auto">{scim.scim_token}</pre>
          </div>
        ) : (
          <div className="flex gap-2">
            <select value={directoryType} onChange={(e) => setDirectoryType(e.target.value)} aria-label="Identity provider" className="rounded-lg border border-border bg-surface px-3 py-2 text-sm">
              <option value="okta-scim-v2">Okta</option>
              <option value="azure-scim-v2">Microsoft Entra ID</option>
              <option value="onelogin-scim-v2">OneLogin</option>
              <option value="jumpcloud-scim-v2">JumpCloud</option>
              <option value="generic-scim-v2">Other (SCIM 2.0)</option>
            </select>
            <Button onClick={() => void run(async () => { const { data } = await api.post('/sso/directory', { type: directoryType }); setScim(data) }, 'Directory created')}>
              Create SCIM endpoint
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}

function ComplianceTab({ toast }: { toast: ReturnType<typeof useToast>['toast'] }) {
  const [content, setContent] = useState('')
  const [audit, setAudit] = useState('')
  const [entries, setEntries] = useState<{ id: string; created_at: string; action: string; user_email: string | null }[]>([])

  useEffect(() => {
    void api.get<{ content_retention_days: number | null; audit_retention_days: number | null }>('/settings/retention').then(({ data }) => {
      setContent(data.content_retention_days?.toString() ?? '')
      setAudit(data.audit_retention_days?.toString() ?? '')
    })
    void api.get('/audit-logs', { params: { limit: 20 } }).then(({ data }) => setEntries(data))
  }, [])

  const save = async () => {
    try {
      await api.put('/settings/retention', {
        content_retention_days: content ? Number(content) : null,
        audit_retention_days: audit ? Number(audit) : null,
      })
      toast('success', 'Retention saved', 'Older data is removed nightly')
    } catch (err) {
      toast('error', errorDetail(err, 'Could not save retention'))
    }
  }

  const download = async (format: 'csv' | 'jsonl') => {
    try {
      const { data } = await api.get(`/audit-logs/export`, { params: { format }, responseType: 'blob' })
      const url = URL.createObjectURL(data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit-log.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast('error', 'Export failed')
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Card className="p-6 space-y-3">
        <h3 className="font-semibold">Data retention</h3>
        <p className="text-xs text-muted">Leave empty to keep data forever. Documents and billing records are never removed automatically.</p>
        <label className="block text-sm" htmlFor="ret-content">Questions, answers and conversations (days)
          <Input id="ret-content" type="number" min={1} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Keep forever" />
        </label>
        <label className="block text-sm" htmlFor="ret-audit">Audit log (days, minimum 90)
          <Input id="ret-audit" type="number" min={90} value={audit} onChange={(e) => setAudit(e.target.value)} placeholder="Keep forever" />
        </label>
        <Button onClick={() => void save()}>Save</Button>
      </Card>
      <Card className="p-6 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Audit log</h3>
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => void download('csv')}>Export CSV</Button>
            <Button size="sm" variant="secondary" onClick={() => void download('jsonl')}>Export JSONL</Button>
          </div>
        </div>
        {entries.map((e) => (
          <div key={e.id} className="flex justify-between text-xs border-b border-border-subtle py-1">
            <span className="font-mono">{e.action}</span>
            <span className="text-muted">{e.user_email ?? 'system'} · {new Date(e.created_at).toLocaleString()}</span>
          </div>
        ))}
      </Card>
    </div>
  )
}

function ApiKeysTab({ toast }: { toast: ReturnType<typeof useToast>['toast'] }) {
  const [keys, setKeys] = useState<ApiKeyItem[]>([])
  const [newKey, setNewKey] = useState('')

  const load = () => void api.get<ApiKeyItem[]>('/api-keys').then(({ data }) => setKeys(data))
  useEffect(() => { load() }, [])

  const create = async () => {
    const { data } = await api.post<{ api_key: string }>('/api-keys', { name: 'Integration', kind: 'secret' })
    setNewKey(data.api_key)
    load()
    toast('success', 'Secret key created', 'Copy it now. It is shown once and must stay on your servers')
  }

  const revoke = async (id: string) => {
    await api.delete(`/api-keys/${id}`)
    load()
    toast('success', 'Key revoked')
  }

  return (
    <Card className="p-6 max-w-2xl">
      <div className="flex justify-between mb-4">
        <h3 className="font-semibold">API Keys</h3>
        <Button size="sm" onClick={() => void create()}>Generate key</Button>
      </div>
      {newKey && <div className="mb-4 p-3 rounded-lg bg-primary-muted font-mono text-sm break-all">{newKey}</div>}
      {keys.map((k) => (
        <div key={k.id} className="flex items-center justify-between py-2 border-b border-border-subtle">
          <div><p className="text-sm">{k.name} <span className="text-xs text-muted">· {k.kind === 'publishable' ? 'widget (query only)' : 'secret'}</span></p><p className="text-xs text-muted font-mono">{k.masked_key}</p></div>
          {k.id !== 'legacy' && <Button variant="danger" size="sm" onClick={() => void revoke(k.id)}>Revoke</Button>}
        </div>
      ))}
    </Card>
  )
}

function BillingTab({ toast }: { toast: ReturnType<typeof useToast>['toast'] }) {
  const [searchParams] = useSearchParams()
  const [sub, setSub] = useState<BillingSubscription | null>(null)
  const [loading, setLoading] = useState(true)
  const upgradePlan = searchParams.get('plan')

  const checkout = async (plan: string) => {
    try {
      const { data } = await api.post<{ checkout_url: string }>('/billing/checkout', { plan })
      window.location.href = data.checkout_url
    } catch {
      toast('error', 'Billing unavailable', 'Configure Stripe keys in .env')
    }
  }

  useEffect(() => {
    void api
      .get<BillingSubscription>('/billing/subscription')
      .then(({ data }) => setSub(data))
      .catch(() => toast('error', 'Failed to load billing'))
      .finally(() => setLoading(false))
  }, [toast])

  useEffect(() => {
    if (!upgradePlan || !sub || searchParams.get('billing') !== 'upgrade') return
    if (['starter', 'pro'].includes(upgradePlan) && sub.plan !== upgradePlan) {
      void checkout(upgradePlan)
    }
  }, [upgradePlan, sub, searchParams])

  const portal = async () => {
    try {
      const { data } = await api.post<{ portal_url: string }>('/billing/portal')
      window.location.href = data.portal_url
    } catch {
      toast('error', 'Portal unavailable')
    }
  }

  if (loading) {
    return (
      <Card className="p-6 max-w-lg space-y-3">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-8 w-full" />
      </Card>
    )
  }
  if (!sub) return null
  return (
    <Card className="p-6 max-w-lg">
      <h3 className="font-semibold mb-2 capitalize">{sub.plan} plan</h3>
      <p className="text-sm text-muted mb-4">Status: {sub.status}</p>
      <UsageBar label="Tokens" used={sub.tokens_used} limit={sub.tokens_limit} />
      <UsageBar label="Storage" unit="bytes" used={sub.storage_used_bytes} limit={sub.storage_limit_bytes} />
      <div className="flex gap-2 mt-4">
        {sub.plan === 'free' && <Button onClick={() => void checkout('starter')}>Upgrade to Starter</Button>}
        {sub.plan === 'starter' && <Button onClick={() => void checkout('pro')}>Upgrade to Pro</Button>}
        <Button variant="secondary" onClick={() => void portal()}>Manage billing</Button>
      </div>
    </Card>
  )
}

function DangerTab({ tenant, toast }: { tenant: ReturnType<typeof useAuthStore.getState>['tenant']; toast: ReturnType<typeof useToast>['toast'] }) {
  return (
    <Card className="p-6 max-w-lg border-danger/30">
      <h3 className="font-semibold text-danger mb-2">Delete workspace</h3>
      <p className="text-sm text-muted mb-4">Permanently delete {tenant?.name} and all data. Contact support to proceed.</p>
      <Button variant="danger" onClick={() => toast('info', 'Contact support', 'Self-service deletion coming soon')}>Delete tenant</Button>
    </Card>
  )
}
