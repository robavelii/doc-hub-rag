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
import { Button, Card, Input, ThemeToggle, useToast } from '../components/ui'
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

  return (
    <div className="flex min-h-screen">
      {/* Left panel — branding (same as login) */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden items-center justify-center p-12">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-accent-blue/10 to-accent-purple/10" />
        <div className="absolute inset-0" style={{ backgroundImage: 'var(--gradient-mesh)' }} />

        <div className="absolute top-1/4 left-1/4 h-64 w-64 rounded-full bg-primary/10 blur-3xl animate-breathe" />
        <div className="absolute bottom-1/3 right-1/4 h-48 w-48 rounded-full bg-accent-blue/10 blur-3xl animate-breathe" style={{ animationDelay: '1s' }} />

        <div className="relative z-10 max-w-md animate-fade-in-up">
          <div className="flex items-center gap-3 mb-8">
            <img src="/brand/logo.svg" alt="Doc-Hub" className="h-12 w-12" />
            <span className="text-2xl font-bold text-text">Doc-Hub</span>
          </div>

          <h1 className="text-4xl font-bold text-text leading-tight mb-4">
            Get started in
            <br />
            <span className="bg-gradient-to-r from-primary to-accent-blue bg-clip-text text-transparent">
              under a minute.
            </span>
          </h1>
          <p className="text-text-secondary text-lg leading-relaxed mb-8">
            Create your workspace, upload documents, and deploy your AI assistant.
            No credit card required.
          </p>

          {/* Steps indicator */}
          <div className="space-y-3">
            {[
              { n: 1, label: 'Create your workspace', done: step !== 'form' },
              { n: 2, label: 'Upload your first documents', done: step === 'success' },
              { n: 3, label: 'Embed the widget on your site', done: false },
            ].map(({ n, label, done }) => (
              <div key={n} className="flex items-center gap-3">
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                    done
                      ? 'bg-primary text-white'
                      : 'border border-border text-muted'
                  }`}
                >
                  {done ? <Check size={14} /> : n}
                </div>
                <span className={done ? 'text-text font-medium' : 'text-muted'}>{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex flex-1 items-center justify-center p-6 lg:p-12 relative">
        <div className="absolute top-4 right-4">
          <ThemeToggle />
        </div>

        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <img src="/brand/logo.svg" alt="Doc-Hub" className="h-10 w-10" />
            <span className="text-xl font-bold text-text">Doc-Hub</span>
          </div>

          {step === 'form' && (
            <Card variant="glass" className="p-8 animate-fade-in">
              <h2 className="text-2xl font-bold text-text mb-1">Create your workspace</h2>
              <p className="text-sm text-muted mb-8">Start building your AI knowledge base</p>

              <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-muted mb-1.5">Company name</label>
                  <Input
                    placeholder="Acme Corp"
                    value={tenantName}
                    onChange={(e) => setTenantName(e.target.value)}
                    icon={<Building2 size={16} />}
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-muted mb-1.5">Email</label>
                  <Input
                    type="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    icon={<Mail size={16} />}
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-muted mb-1.5">Password</label>
                  <div className="relative">
                    <Input
                      type={showPassword ? 'text' : 'password'}
                      placeholder="At least 6 characters"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      icon={<Lock size={16} />}
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-text transition-colors"
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  {/* Password strength */}
                  {password.length > 0 && passwordStrength && (
                    <div className="mt-2 flex gap-1">
                      {[1, 2, 3, 4].map((level) => (
                        <div
                          key={level}
                          className="h-1 flex-1 rounded-full transition-colors duration-300"
                          style={{
                            backgroundColor:
                              level <= passwordStrength.level
                                ? passwordStrength.color
                                : 'var(--border)',
                          }}
                        />
                      ))}
                      <span className="text-[10px] ml-1 text-muted">{passwordStrength.label}</span>
                    </div>
                  )}
                </div>

                {error && (
                  <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2 text-sm text-danger animate-fade-in">
                    {error}
                  </div>
                )}

                <Button type="submit" className="w-full" loading={loading} size="lg">
                  Create workspace
                </Button>
              </form>

              <div className="mt-6 text-center">
                <p className="text-sm text-muted">
                  Already have an account?{' '}
                  <Link
                    to="/login"
                    className="font-medium text-primary hover:text-primary-hover transition-colors"
                  >
                    Sign in
                  </Link>
                </p>
              </div>
            </Card>
          )}

          {step === 'upload' && (
            <Card variant="glass" className="p-8 animate-fade-in">
              <h2 className="text-2xl font-bold text-text mb-1">Upload your first document</h2>
              <p className="text-sm text-muted mb-6">Optional — you can skip and do this later</p>
              <UploadZone onUploadComplete={() => setStep('success')} />
              <Button variant="ghost" className="w-full mt-4" onClick={() => setStep('success')}>
                Skip for now
              </Button>
            </Card>
          )}

          {step === 'success' && (
            <Card variant="glass" className="p-8 animate-scale-in text-center">
              <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-primary-muted mb-6">
                <Check size={32} className="text-primary" />
              </div>

              <h2 className="text-2xl font-bold text-text mb-2">Workspace created!</h2>
              <p className="text-sm text-muted mb-6">
                Your API key is shown below. Save it — it won't be shown again.
              </p>

              {apiKey && (
                <div className="relative mb-6">
                  <div className="flex items-center gap-2 rounded-lg bg-surface-solid border border-border p-3">
                    <code className="flex-1 text-sm font-mono text-text truncate">
                      {apiKey}
                    </code>
                    <button
                      onClick={() => void handleCopyKey()}
                      className="shrink-0 p-1.5 rounded-md text-muted hover:text-text hover:bg-surface-2 transition-colors"
                    >
                      {copied ? <Check size={16} className="text-success" /> : <Copy size={16} />}
                    </button>
                  </div>
                </div>
              )}

              <Button
                onClick={() =>
                  navigate(
                    planIntent && planIntent !== 'free'
                      ? `/settings?billing=upgrade&plan=${planIntent}`
                      : '/documents'
                  )
                }
                className="w-full"
                size="lg"
              >
                {planIntent && planIntent !== 'free' ? 'Continue to billing' : 'Upload your first document'}
              </Button>
              <button
                onClick={() => navigate('/chat')}
                className="mt-3 text-sm text-muted hover:text-text transition-colors"
              >
                Skip for now →
              </button>
            </Card>
          )}
        </div>
      </div>
    </div>
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
