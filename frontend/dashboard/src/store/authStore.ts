import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { TenantSummary, UserSummary } from '@shared/types'
import api from '../lib/api'

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: UserSummary | null
  tenant: TenantSummary | null
  apiKey: string | null
  login: (email: string, password: string, remember?: boolean) => Promise<void>
  register: (tenantName: string, email: string, password: string) => Promise<{ api_key?: string }>
  logout: () => void
}

function decodeJwtPayload(token: string): {
  sub: string
  tenant_id: string
  role: string
  is_superadmin?: boolean
} {
  const payload = token.split('.')[1]
  if (!payload) throw new Error('Invalid token')
  return JSON.parse(atob(payload)) as {
    sub: string
    tenant_id: string
    role: string
    is_superadmin?: boolean
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      tenant: null,
      apiKey: null,

      login: async (email, password, remember = false) => {
        const { data } = await api.post('/auth/login', { email, password })
        localStorage.setItem('access_token', data.access_token as string)
        if (data.refresh_token) {
          if (remember) localStorage.setItem('refresh_token', data.refresh_token as string)
        }
        api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`
        const payload = decodeJwtPayload(data.access_token as string)
        set({
          accessToken: data.access_token as string,
          refreshToken: remember ? (data.refresh_token as string) : null,
          user: (data.user as UserSummary) ?? {
            id: payload.sub,
            email,
            role: payload.role as UserSummary['role'],
            is_superadmin: payload.is_superadmin,
          },
          tenant: (data.tenant as TenantSummary) ?? { id: payload.tenant_id, name: '', slug: '' },
        })
      },

      register: async (tenantName, email, password) => {
        const { data } = await api.post('/auth/register', {
          tenant_name: tenantName,
          email,
          password,
        })
        localStorage.setItem('access_token', data.access_token as string)
        if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token as string)
        api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`
        set({
          accessToken: data.access_token as string,
          refreshToken: (data.refresh_token as string) ?? null,
          tenant: data.tenant as TenantSummary,
          apiKey: (data.api_key as string) ?? null,
          user: (data.user as UserSummary) ?? { id: '', email, role: 'owner', is_superadmin: false },
        })
        return { api_key: data.api_key as string | undefined }
      },

      logout: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        delete api.defaults.headers.common['Authorization']
        set({ accessToken: null, refreshToken: null, user: null, tenant: null, apiKey: null })
      },
    }),
    { name: 'auth-store' }
  )
)
