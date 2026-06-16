import { FormEvent, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Eye, EyeOff, Lock, Mail } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { Button, Card, Input, ThemeToggle, useToast } from '../components/ui'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(false)
  const [loading, setLoading] = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()
  const { toast } = useToast()

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
    <div className="flex min-h-screen">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden items-center justify-center p-12">
        {/* Animated gradient background */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-accent-blue/10 to-accent-purple/10" />
        <div className="absolute inset-0" style={{ backgroundImage: 'var(--gradient-mesh)' }} />

        {/* Floating orbs */}
        <div className="absolute top-1/4 left-1/4 h-64 w-64 rounded-full bg-primary/10 blur-3xl animate-breathe" />
        <div className="absolute bottom-1/3 right-1/4 h-48 w-48 rounded-full bg-accent-blue/10 blur-3xl animate-breathe" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 right-1/3 h-32 w-32 rounded-full bg-accent-purple/10 blur-3xl animate-breathe" style={{ animationDelay: '0.5s' }} />

        <div className="relative z-10 max-w-md animate-fade-in-up">
          {/* Logo */}
          <div className="flex items-center gap-3 mb-8">
            <img src="/brand/logo.svg" alt="Doc-Hub" className="h-12 w-12" />
            <span className="text-2xl font-bold text-text">Doc-Hub</span>
          </div>

          <h1 className="text-4xl font-bold text-text leading-tight mb-4">
            Your knowledge,
            <br />
            <span className="bg-gradient-to-r from-primary to-accent-blue bg-clip-text text-transparent">
              AI-powered.
            </span>
          </h1>
          <p className="text-text-secondary text-lg leading-relaxed mb-8">
            Upload your documents, train your private AI assistant, and embed it anywhere. 
            Enterprise-grade RAG with complete tenant isolation.
          </p>

          {/* Feature pills */}
          <div className="flex flex-wrap gap-2">
            {['Multi-tenant', 'SSE Streaming', 'Hybrid Search', 'Embeddable Widget'].map((f) => (
              <span
                key={f}
                className="rounded-full border border-border-subtle bg-surface-2/30 px-3 py-1.5 text-xs text-muted backdrop-blur-sm"
              >
                {f}
              </span>
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

          <Card variant="glass" className="p-8">
            <h2 className="text-2xl font-bold text-text mb-1">Welcome back</h2>
            <p className="text-sm text-muted mb-8">Sign in to your dashboard</p>

            <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
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
                    placeholder="••••••••"
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
              </div>

              <label className="flex items-center gap-2 text-sm text-muted cursor-pointer">
                <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="rounded" />
                Remember me
              </label>

              <Button type="submit" className="w-full" loading={loading} size="lg">
                Sign in
              </Button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-sm text-muted">
                Don't have an account?{' '}
                <Link
                  to="/register"
                  className="font-medium text-primary hover:text-primary-hover transition-colors"
                >
                  Create one
                </Link>
              </p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
