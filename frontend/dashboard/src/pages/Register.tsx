import { FormEvent, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  Building2,
  Check,
  Copy,
  Eye,
  EyeOff,
  Lock,
  Mail,
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import UploadZone from '../components/UploadZone'
import AuthLayout from '../components/AuthLayout'
import { Button, Input, useToast } from '../components/ui'
import { cn } from '../lib/cn'
import { copyText } from '../lib/copy'

type Step = 'form' | 'upload' | 'success'

export default function Register() {
  const [step, setStep] = useState<Step>('form')
  const [tenantName, setTenantName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [copied, setCopied] = useState(false)
  const { register } = useAuthStore()
  const navigate = useNavigate()
  const { toast } = useToast()
  const planIntent = new URLSearchParams(window.location.search).get('plan')

  const passwordStrength = getPasswordStrength(password)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (password.length < 12) {
      const msg = 'Password must be at least 12 characters'
      setError(msg)
      toast('error', msg)
      return
    }
    setError('')
    setLoading(true)
    try {
      const result = await register(tenantName, email, password)
      setApiKey(result.api_key || '')
      setStep('upload')
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err
          ? String(
              (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            )
          : 'Registration failed'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const handleCopyKey = async () => {
    const ok = await copyText(apiKey)
    if (ok) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const steps = [
    { n: 1, label: 'Create your workspace', done: step !== 'form' },
    { n: 2, label: 'Upload your first documents', done: step === 'success' },
    { n: 3, label: 'Embed the widget on your site', done: false },
  ]

  return (
    <AuthLayout
      aside={
        <>
          <h1 className="text-[34px] font-semibold leading-[1.1] tracking-tight text-text">Get started in under a minute.</h1>
          <p className="mt-4 text-[15px] leading-relaxed text-text-secondary">
            Create your workspace, upload documents, and deploy your assistant. The free plan needs no card.
          </p>
          <ol className="mt-8 space-y-3" aria-label="Setup progress">
            {steps.map(({ n, label, done }) => (
              <li key={n} className="flex items-center gap-3 text-[15px]">
                <span
                  className={cn(
                    'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
                    done ? 'bg-primary text-primary-fg' : 'border border-border-strong text-muted'
                  )}
                  aria-hidden="true"
                >
                  {done ? <Check size={13} strokeWidth={2.5} /> : n}
                </span>
                <span className={done ? 'font-medium text-text' : 'text-muted'}>
                  {label}
                  {done && <span className="sr-only"> (done)</span>}
                </span>
              </li>
            ))}
          </ol>
        </>
      }
    >
      {step === 'form' && (
        <>
          <h2 className="text-2xl font-semibold tracking-tight text-text">Create your workspace</h2>
          <p className="mb-8 mt-1 text-sm text-muted">Start building your knowledge base</p>

          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            <div>
              <label htmlFor="reg-company" className="mb-1.5 block text-sm font-medium text-text-secondary">
                Company name
              </label>
              <Input
                id="reg-company"
                autoComplete="organization"
                placeholder="Acme Corp"
                value={tenantName}
                onChange={(e) => setTenantName(e.target.value)}
                icon={<Building2 size={16} />}
                required
              />
            </div>

            <div>
              <label htmlFor="reg-email" className="mb-1.5 block text-sm font-medium text-text-secondary">
                Email
              </label>
              <Input
                id="reg-email"
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
              <label htmlFor="reg-password" className="mb-1.5 block text-sm font-medium text-text-secondary">
                Password
              </label>
              <div className="relative">
                <Input
                  id="reg-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="At least 12 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  icon={<Lock size={16} />}
                  className="pr-10"
                  error={!!error && password.length < 12}
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
              {password.length > 0 && passwordStrength && (
                <div className="mt-2 flex items-center gap-1" aria-live="polite">
                  {[1, 2, 3, 4].map((level) => (
                    <div
                      key={level}
                      className="h-1 flex-1 rounded-full transition-colors duration-short"
                      style={{
                        backgroundColor: level <= passwordStrength.level ? passwordStrength.color : 'var(--border)',
                      }}
                    />
                  ))}
                  <span className="ml-1.5 w-12 text-xs text-muted">{passwordStrength.label}</span>
                </div>
              )}
            </div>

            {error && (
              <p role="alert" className="rounded-lg border border-danger/25 bg-danger/10 px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" loading={loading} size="lg">
              Create workspace
            </Button>
          </form>

          <p className="mt-8 text-center text-sm text-muted">
            Already have an account?{' '}
            <Link to="/login" className="font-medium text-text underline decoration-border-strong underline-offset-4 hover:decoration-accent">
              Sign in
            </Link>
          </p>
        </>
      )}

      {step === 'upload' && (
        <>
          <h2 className="text-2xl font-semibold tracking-tight text-text">Upload your first document</h2>
          <p className="mb-6 mt-1 text-sm text-muted">Optional. You can skip this and do it later.</p>
          <UploadZone onUploadComplete={() => setStep('success')} />
          <Button variant="ghost" className="mt-4 w-full" onClick={() => setStep('success')}>
            Skip for now
          </Button>
        </>
      )}

      {step === 'success' && (
        <>
          <span className="mb-6 inline-flex h-11 w-11 items-center justify-center rounded-full bg-primary text-primary-fg" aria-hidden="true">
            <Check size={22} strokeWidth={2.5} />
          </span>
          <h2 className="text-2xl font-semibold tracking-tight text-text">Workspace created</h2>
          <p className="mb-6 mt-1 text-sm text-muted">Your API key is below. Save it now: it won&rsquo;t be shown again.</p>

          {apiKey && (
            <div className="mb-6 flex items-center gap-2 rounded-lg border border-border bg-surface p-2 pl-3 shadow-sm">
              <code className="flex-1 truncate font-mono text-sm text-text">{apiKey}</code>
              <button
                type="button"
                onClick={() => void handleCopyKey()}
                aria-label={copied ? 'Copied' : 'Copy API key'}
                className="shrink-0 rounded-md p-1.5 text-muted transition-colors duration-micro hover:bg-primary-muted hover:text-text"
              >
                {copied ? <Check size={16} className="text-success" /> : <Copy size={16} />}
              </button>
            </div>
          )}

          <Button
            onClick={() =>
              navigate(planIntent && planIntent !== 'free' ? `/settings?billing=upgrade&plan=${planIntent}` : '/documents')
            }
            className="w-full"
            size="lg"
          >
            {planIntent && planIntent !== 'free' ? 'Continue to billing' : 'Upload your first document'}
          </Button>
          <Button variant="ghost" className="mt-2 w-full" onClick={() => navigate('/chat')}>
            Skip for now
          </Button>
        </>
      )}
    </AuthLayout>
  )
}

function getPasswordStrength(password: string) {
  let score = 0
  if (password.length >= 12) score++
  if (password.length >= 16) score++
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++
  if (/[0-9]/.test(password) || /[^A-Za-z0-9]/.test(password)) score++

  const levels: { level: number; label: string; color: string }[] = [
    { level: 0, label: '', color: 'var(--border)' },
    { level: 1, label: 'Weak', color: 'var(--danger)' },
    { level: 2, label: 'Fair', color: 'var(--warning)' },
    { level: 3, label: 'Good', color: 'var(--info)' },
    { level: 4, label: 'Strong', color: 'var(--success)' },
  ]
  return levels[score] || levels[0]
}
