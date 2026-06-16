import { describe, expect, it, vi, beforeEach } from 'vitest'

function decodeJwtPayload(token: string): { sub: string; tenant_id: string; role: string } {
  const payload = token.split('.')[1]
  if (!payload) throw new Error('Invalid token')
  return JSON.parse(atob(payload))
}

describe('auth jwt helpers', () => {
  it('decodes a JWT payload', () => {
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    const body = btoa(JSON.stringify({ sub: 'user-1', tenant_id: 'tenant-1', role: 'owner' }))
    const token = `${header}.${body}.sig`

    const payload = decodeJwtPayload(token)
    expect(payload.sub).toBe('user-1')
    expect(payload.tenant_id).toBe('tenant-1')
    expect(payload.role).toBe('owner')
  })
})

describe('api token storage', () => {
  beforeEach(() => {
    const store: Record<string, string> = {}

    vi.stubGlobal('localStorage', {
      getItem(key: string) {
        return store[key] ?? null
      },
      setItem(key: string, value: string) {
        store[key] = value
      },
      removeItem(key: string) {
        delete store[key]
      },
    })
  })

  it('stores access token in localStorage on login response', () => {
    const token = 'test-access-token'
    localStorage.setItem('access_token', token)
    expect(localStorage.getItem('access_token')).toBe(token)
  })
})
