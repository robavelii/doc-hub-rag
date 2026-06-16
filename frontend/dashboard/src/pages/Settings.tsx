import { useEffect, useState } from 'react'
import type { ApiKeyItem, BillingSubscription, TeamMember } from '@shared/types'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { useSearchParams } from 'react-router-dom'
import { Button, Card, Input, Skeleton, useToast } from '../components/ui'
import UsageBar from '../components/UsageBar'
import { cn } from '../lib/cn'

type Tab = 'profile' | 'team' | 'keys' | 'billing' | 'danger'

const TABS: { id: Tab; label: string }[] = [
  { id: 'profile', label: 'Profile' },
  { id: 'team', label: 'Team' },
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

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Settings</h1>
      <div className="flex gap-1 mb-6 border-b border-border overflow-x-auto">
        {TABS.map((t) => (
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
      {inviteToken && <p className="mt-2 text-xs text-muted font-mono">Token: {inviteToken}</p>}
    </Card>
  )
}

function ApiKeysTab({ toast }: { toast: ReturnType<typeof useToast>['toast'] }) {
  const [keys, setKeys] = useState<ApiKeyItem[]>([])
  const [newKey, setNewKey] = useState('')

  const load = () => void api.get<ApiKeyItem[]>('/api-keys').then(({ data }) => setKeys(data))
  useEffect(() => { load() }, [])

  const create = async () => {
    const { data } = await api.post<{ api_key: string }>('/api-keys', { name: 'Integration' })
    setNewKey(data.api_key)
    load()
    toast('success', 'API key created', 'Copy it now — shown once')
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
          <div><p className="text-sm">{k.name}</p><p className="text-xs text-muted font-mono">{k.masked_key}</p></div>
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
      <UsageBar label="Storage" used={sub.storage_used_bytes} limit={sub.storage_limit_bytes} />
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
