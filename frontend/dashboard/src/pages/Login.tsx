import { FormEvent, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff, Lock, Mail } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import api from '../lib/api'
import AuthLayout from '../components/AuthLayout'
import { Button, Input, useToast } from '../components/ui'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(false)
  const [loading, setLoading] = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()
  const { toast } = useToast()

  const startSso = async () => {
    if (!email.includes('@')) {
      toast('error', 'Enter your work email first')
      return
    }
    try {
      const { data } = await api.get<{ sso: boolean }>('/auth/sso/discover', { params: { email } })
      if (!data.sso) {
        toast('error', 'Single sign-on is not set up for this email domain')
        return
      }
      window.location.href = `${api.defaults.baseURL ?? ''}/auth/sso/start?email=${encodeURIComponent(email)}`
    } catch {
      toast('error', 'Could not reach the server')
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await login(email, password, remember)
      toast('success', 'Welcome back!')
      navigate('/chat')
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err
          ? String((err as { response?: { data?: { detail?: string } } }).response?.data?.detail)
          : 'Authentication failed'
      toast('error', message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      aside={
        <>
          <h1 className="text-[34px] font-semibold leading-[1.1] tracking-tight text-text">Your documents, answered.</h1>
          <p className="mt-4 text-[15px] leading-relaxed text-text-secondary">
            Upload your documents, get a private assistant that cites them, and embed it anywhere. Every workspace is
            isolated from every other.
          </p>
          <p className="mt-6 text-sm text-muted">Multi-tenant, streaming answers, hybrid search, an embeddable widget.</p>
        </>
      }
    >
      <h2 className="text-2xl font-semibold tracking-tight text-text">Welcome back</h2>
      <p className="mb-8 mt-1 text-sm text-muted">Sign in to your dashboard</p>

      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        <div>
          <label htmlFor="login-email" className="mb-1.5 block text-sm font-medium text-text-secondary">
            Email
          </label>
          <Input
            id="login-email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            icon={<Mail size={16} />}
            required
          />
        </div>

        <div>
          <label htmlFor="login-password" className="mb-1.5 block text-sm font-medium text-text-secondary">
            Password
          </label>
          <div className="relative">
            <Input
              id="login-password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              placeholder="Your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              icon={<Lock size={16} />}
              className="pr-10"
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted transition-colors duration-micro hover:text-text"
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

        <label className="flex cursor-pointer items-center gap-2 text-sm text-text-secondary">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="h-4 w-4 rounded border-border-strong accent-primary"
          />
          Remember me
        </label>

        <Button type="submit" className="w-full" loading={loading} size="lg">
          Sign in
        </Button>
        <Button type="button" variant="secondary" className="w-full" size="lg" onClick={() => void startSso()}>
          Continue with SSO
        </Button>
      </form>

      <p className="mt-8 text-center text-sm text-muted">
        Don&rsquo;t have an account?{' '}
        <Link to="/register" className="font-medium text-text underline decoration-border-strong underline-offset-4 hover:decoration-accent">
          Create one
        </Link>
      </p>
    </AuthLayout>
  )
}
