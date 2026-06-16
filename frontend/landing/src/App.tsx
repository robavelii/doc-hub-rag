const DASHBOARD_URL = import.meta.env.VITE_DASHBOARD_URL || 'http://localhost:3000'

const features = [
  {
    title: 'Document Intelligence',
    desc: 'Upload PDFs, DOCX, and URLs. Automatic chunking, embedding, and indexing with pgvector.',
    icon: '📄',
  },
  {
    title: 'Streaming RAG Chat',
    desc: 'Ask questions and get cited answers in real time with confidence scores and source excerpts.',
    icon: '💬',
  },
  {
    title: 'Embeddable Widget',
    desc: 'Drop a chat widget on any website. Domain-restricted, fully customizable, API-key secured.',
    icon: '🔌',
  },
  {
    title: 'Multi-Tenant Isolation',
    desc: 'Row-level security, per-tenant API keys, and usage limits. Built for SaaS from day one.',
    icon: '🏢',
  },
  {
    title: 'Usage Analytics',
    desc: 'Track tokens, queries, latency, and storage. Plan-based limits with upgrade paths.',
    icon: '📊',
  },
  {
    title: 'Provider Flexibility',
    desc: 'OpenAI, Ollama, or fallback chains. Swap AI providers without changing your integration.',
    icon: '⚡',
  },
]

const plans = [
  {
    name: 'Free',
    planId: 'free',
    price: '$0',
    period: '/mo',
    tokens: '100K tokens',
    storage: '100 MB',
    docs: '10 documents',
    cta: 'Start Free',
    highlight: false,
  },
  {
    name: 'Starter',
    planId: 'starter',
    price: '$29',
    period: '/mo',
    tokens: '1M tokens',
    storage: '1 GB',
    docs: '100 documents',
    cta: 'Get Starter',
    highlight: true,
  },
  {
    name: 'Pro',
    planId: 'pro',
    price: '$99',
    period: '/mo',
    tokens: '10M tokens',
    storage: '10 GB',
    docs: 'Unlimited',
    cta: 'Go Pro',
    highlight: false,
  },
]

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <img src="/brand/logo.svg" alt="Doc-Hub" className="h-8 w-8" />
      <span className="text-lg font-semibold tracking-tight">
        Doc<span className="gradient-text">-Hub</span>
      </span>
    </div>
  )
}

export default function App() {
  return (
    <div className="mesh-bg min-h-screen">
      <nav className="glass sticky top-0 z-50 border-b border-white/5">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Logo />
          <div className="flex items-center gap-4">
            <a href="#features" className="text-sm text-muted hover:text-text transition-colors">
              Features
            </a>
            <a href="#pricing" className="text-sm text-muted hover:text-text transition-colors">
              Pricing
            </a>
            <a
              href={`${DASHBOARD_URL}/login`}
              className="text-sm text-muted hover:text-text transition-colors"
            >
              Sign in
            </a>
            <a
              href={`${DASHBOARD_URL}/register`}
              className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-bg transition hover:opacity-90"
            >
              Get Started
            </a>
          </div>
        </div>
      </nav>

      <section className="mx-auto max-w-6xl px-6 py-24 text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm text-muted">
          <span className="h-2 w-2 rounded-full bg-brand animate-pulse" />
          Multi-tenant RAG platform
        </div>
        <h1 className="mb-6 text-5xl font-bold leading-tight tracking-tight md:text-6xl">
          Turn documents into
          <br />
          <span className="gradient-text">AI-powered answers</span>
        </h1>
        <p className="mx-auto mb-10 max-w-2xl text-lg text-muted">
          Doc-Hub lets you upload knowledge bases, chat with cited responses, and embed
          a widget on any site — with full tenant isolation and usage controls.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4">
          <a
            href={`${DASHBOARD_URL}/register`}
            className="rounded-xl bg-brand px-8 py-3.5 text-base font-semibold text-bg shadow-lg shadow-brand/20 transition hover:opacity-90"
          >
            Start for free
          </a>
          <a
            href="#features"
            className="rounded-xl border border-white/10 px-8 py-3.5 text-base font-medium transition hover:bg-white/5"
          >
            See features
          </a>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="mb-4 text-center text-3xl font-bold">Everything you need</h2>
        <p className="mb-12 text-center text-muted">Production-ready RAG infrastructure out of the box</p>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="glass rounded-2xl p-6 transition hover:border-brand/20">
              <div className="mb-4 text-3xl">{f.icon}</div>
              <h3 className="mb-2 text-lg font-semibold">{f.title}</h3>
              <p className="text-sm leading-relaxed text-muted">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="mb-4 text-center text-3xl font-bold">Simple pricing</h2>
        <p className="mb-12 text-center text-muted">Scale as your knowledge base grows</p>
        <div className="grid gap-6 md:grid-cols-3">
          {plans.map((p) => (
            <div
              key={p.name}
              className={`glass rounded-2xl p-8 ${p.highlight ? 'border-brand/40 ring-1 ring-brand/20' : ''}`}
            >
              {p.highlight && (
                <span className="mb-4 inline-block rounded-full bg-brand/10 px-3 py-1 text-xs font-medium text-brand">
                  Most popular
                </span>
              )}
              <h3 className="text-xl font-semibold">{p.name}</h3>
              <div className="my-4">
                <span className="text-4xl font-bold">{p.price}</span>
                <span className="text-muted">{p.period}</span>
              </div>
              <ul className="mb-8 space-y-2 text-sm text-muted">
                <li>{p.tokens}</li>
                <li>{p.storage} storage</li>
                <li>{p.docs}</li>
              </ul>
              <a
                href={p.planId === 'free' ? `${DASHBOARD_URL}/register` : `${DASHBOARD_URL}/register?plan=${p.planId}`}
                className={`block rounded-lg py-2.5 text-center text-sm font-medium transition ${
                  p.highlight
                    ? 'bg-brand text-bg hover:opacity-90'
                    : 'border border-white/10 hover:bg-white/5'
                }`}
              >
                {p.cta}
              </a>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20 text-center">
        <div className="glass rounded-3xl p-12">
          <h2 className="mb-4 text-3xl font-bold">Ready to build your knowledge hub?</h2>
          <p className="mb-8 text-muted">Get started in minutes. No credit card required.</p>
          <a
            href={`${DASHBOARD_URL}/register`}
            className="inline-block rounded-xl bg-brand px-8 py-3.5 text-base font-semibold text-bg transition hover:opacity-90"
          >
            Create your workspace
          </a>
        </div>
      </section>

      <footer className="border-t border-white/5 py-8 text-center text-sm text-muted">
        <Logo />
        <p className="mt-4">&copy; {new Date().getFullYear()} Doc-Hub. All rights reserved.</p>
      </footer>
    </div>
  )
}
