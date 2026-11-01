import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { Card } from '../components/ui'

const MESSAGES: Record<string, string> = {
  sso_expired: 'The sign-in link expired. Please try again.',
  sso_failed: 'Single sign-on did not complete. Please try again or contact your administrator.',
  account_suspended: 'This workspace is suspended.',
}

export default function SsoCallback() {
  const loginWithTokens = useAuthStore((s) => s.loginWithTokens)
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1))
    // Drop the tokens from the address bar and history right away.
    window.history.replaceState(null, '', window.location.pathname)
    const access = params.get('access_token')
    if (access) {
      loginWithTokens(access, params.get('refresh_token'))
      navigate('/chat', { replace: true })
      return
    }
    const code = params.get('error') ?? 'sso_failed'
    setError(MESSAGES[code] ?? code)
  }, [loginWithTokens, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="p-6 max-w-md text-center">
        {error ? (
          <>
            <p className="text-sm mb-4">{error}</p>
            <Link to="/login" className="text-primary text-sm font-medium">Back to sign in</Link>
          </>
        ) : (
          <p className="text-sm text-muted">Signing you in…</p>
        )}
      </Card>
    </div>
  )
}
