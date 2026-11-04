const DASHBOARD_URL = import.meta.env.VITE_DASHBOARD_URL || 'http://localhost:3000'

const features = [
  {
    title: 'Document intelligence',
    desc: 'Upload PDF, Word, PowerPoint, Excel, CSV, Markdown, HTML, email or text files, and URLs. Automatic chunking, embedding, and indexing with pgvector.',
  },
  {
    title: 'Streaming RAG chat',
    desc: 'Ask questions and get cited answers in real time with confidence scores and source excerpts.',
  },
  {
    title: 'Embeddable widget',
    desc: 'Drop a chat widget on any website. Domain-restricted, fully customizable, API-key secured.',
  },
  {
    title: 'Multi-tenant isolation',
    desc: 'Row-level security, per-tenant API keys, and usage limits. Built for SaaS from day one.',
  },
  {
    title: 'Usage analytics',
    desc: 'Track tokens, queries, latency, and storage. Plan-based limits with upgrade paths.',
  },
  {
    title: 'Provider flexibility',
    desc: 'Gemini, OpenAI, any OpenAI-compatible endpoint, or Ollama, with fallback chains. Swap AI providers without changing your integration.',
  },
]

const plans = [
  { name: 'Free', planId: 'free', price: '$0', period: '/mo', tokens: '100K tokens', storage: '100 MB', docs: '10 documents', cta: 'Start Free', highlight: false },
  { name: 'Starter', planId: 'starter', price: '$29', period: '/mo', tokens: '1M tokens', storage: '1 GB', docs: '100 documents', cta: 'Get Starter', highlight: true },
  { name: 'Pro', planId: 'pro', price: '$99', period: '/mo', tokens: '10M tokens', storage: '10 GB', docs: 'Unlimited', cta: 'Go Pro', highlight: false },
]

const origin = typeof window !== 'undefined' ? window.location.origin : 'https://your-doc-hub'

function Wordmark({ className = '' }: { className?: string }) {
  return <span className={`font-semibold tracking-[-0.03em] text-text ${className}`}>Doc-Hub</span>
}

function Cite({ n }: { n: number }) {
  return (
    <span className="cite" aria-label={`source ${n}`}>
      {n}
    </span>
  )
}

/* The signature: an answer sheet whose numbers point at a source card laid on the desk */
function AnswerDesk() {
  return (
    <figure className="m-0 min-w-0">
      <div className="desk relative overflow-hidden rounded-2xl p-5 sm:p-8 lg:h-[560px] lg:p-0">
        <div className="stock sheet relative rounded-lg p-6 sm:p-7 lg:absolute lg:left-[6%] lg:top-[8%] lg:w-[80%]">
          <p className="play-line ml-auto w-fit max-w-[85%] rounded-2xl bg-surface-3 px-4 py-2 text-[15px]" style={{ ['--i' as string]: 0 }}>
            How much annual leave do we get?
          </p>
          <p className="play-line mt-5 text-sm font-semibold" style={{ ['--i' as string]: 1 }}>
            Doc-Hub
          </p>
          <p className="play-line mt-1.5 text-[17px] leading-relaxed" style={{ ['--i' as string]: 1 }}>
            Full-time staff get 25 days of paid leave a year
            <Cite n={1} />.
          </p>
          <p className="play-line mt-2 text-[17px] leading-relaxed" style={{ ['--i' as string]: 2 }}>
            Up to 5 unused days carry into the first quarter
            <Cite n={1} />, and expire on 31 March
            <Cite n={2} />.
          </p>
          <ul className="play-line mt-5 flex flex-wrap gap-2 text-xs" style={{ ['--i' as string]: 3 }} aria-label="Sources">
            <li className="rounded-md border border-border bg-surface px-2 py-1 text-text-secondary">
              <span className="mr-1.5 font-semibold text-accent">1</span>staff-handbook.pdf
            </li>
            <li className="rounded-md border border-border bg-surface px-2 py-1 text-text-secondary">
              <span className="mr-1.5 font-semibold text-accent">2</span>leave-policy.docx
            </li>
          </ul>
        </div>

        <div className="play-card stock relative mt-5 -rotate-2 rounded-md p-5 lg:absolute lg:bottom-[7%] lg:right-[5%] lg:mt-0 lg:w-[54%]">
          <p className="text-xs text-muted">staff-handbook.pdf, page 12</p>
          <p className="mt-2 text-[15px] leading-relaxed">
            Full-time employees accrue <span className="passage-mark">25 days of paid annual leave</span> per calendar year,
            pro-rated for part-time contracts.
          </p>
          <span className="play-press pressed absolute -top-3 right-5 bg-transparent text-lg" aria-hidden="true">
            Cited
          </span>
        </div>
      </div>
      <figcaption className="mt-3 text-sm text-muted">
        An answer from an example handbook. Each number opens the passage it came from.
      </figcaption>
    </figure>
  )
}

function EmbedSnippet() {
  return (
    <pre className="code m-0 overflow-x-auto whitespace-pre text-text">
      <code>
        <span className="tok-tag">{'<div id="assistant"></div>'}</span>
        {'\n'}
        <span className="tok-tag">{'<script src='}</span>
        <span className="tok-str">{`"${origin}/widget/widget.js"`}</span>
        <span className="tok-tag">{'></script>'}</span>
        {'\n'}
        <span className="tok-tag">{'<script>'}</span>
        {'\n  RAGWidget.init({\n    apiKey: '}
        <span className="tok-str">{"'pk_your_widget_key'"}</span>
        {',\n    containerId: '}
        <span className="tok-str">{"'assistant'"}</span>
        {',\n    apiBase: '}
        <span className="tok-str">{`'${origin}/api'`}</span>
        {'\n  })\n'}
        <span className="tok-tag">{'</script>'}</span>
      </code>
    </pre>
  )
}

export default function App() {
  return (
    <>
      {/* Roughens the pressed "Cited" stamp so the ink looks uneven */}
      <svg width="0" height="0" className="absolute" aria-hidden="true" focusable="false">
        <filter id="press">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="4" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="1.6" />
        </filter>
      </svg>

      <header className="sticky top-0 z-50 border-b border-border bg-bg">
        <nav className="container flex h-[72px] items-center justify-between gap-6" aria-label="Main">
          <a href="#top" className="rounded-md text-xl">
            <Wordmark />
          </a>
          <div className="flex items-center gap-2 sm:gap-6">
            <a href="#features" className="nav-link hidden text-[15px] sm:inline">
              Features
            </a>
            <a href="#pricing" className="nav-link hidden text-[15px] sm:inline">
              Pricing
            </a>
            <a href={`${DASHBOARD_URL}/login`} className="nav-link text-[15px]">
              Sign in
            </a>
            <a href={`${DASHBOARD_URL}/register`} className="btn btn-ink btn-sm">
              Get started
            </a>
          </div>
        </nav>
      </header>

      <main id="top">
        <section className="flex min-h-[calc(100dvh-72px)] items-center py-12 lg:py-10">
          <div className="container grid items-center gap-x-24 gap-y-12 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <div>
              <h1 className="display">Turn documents into cited answers.</h1>
              <p className="lead mt-6 max-w-[30ch] text-text-secondary">
                Ask your documents anything and see the source behind every answer.
              </p>
              <div className="mt-9 flex flex-wrap gap-3">
                <a href={`${DASHBOARD_URL}/register`} className="btn btn-ink">
                  Start for free
                </a>
                <a href="#features" className="link inline-flex min-h-[48px] items-center px-2 text-[15px] font-medium">
                  See features
                </a>
              </div>
              <p className="mt-4 text-sm text-muted">The free plan needs no card.</p>
            </div>
            <AnswerDesk />
          </div>
        </section>

        <section className="pb-[var(--section-gap)] pt-[var(--section-gap-s)]" aria-labelledby="at-work">
          <div className="container">
            <div className="grid gap-6 lg:grid-cols-12 lg:items-end">
              <h2 id="at-work" className="section-head lg:col-span-6">
                Ask, read, check the source.
              </h2>
              <p className="lead text-text-secondary lg:col-span-5 lg:col-start-8">
                Upload a knowledge base, chat with cited responses, and open the passage behind any answer.
              </p>
            </div>
            <figure className="m-0 mt-14">
              <img
                src="/screens/dashboard-chat.webp"
                width={2880}
                height={1720}
                loading="lazy"
                decoding="async"
                alt="The Doc-Hub dashboard: a conversation history on the left, an answer with numbered citations, and the source passage opened under it."
                className="block h-auto w-full rounded-xl border border-border shadow-[var(--edge-stock),var(--cast-sheet)]"
              />
              <figcaption className="mt-3 text-sm text-muted">
                The dashboard. Conversation history on the left, sources under every answer.
              </figcaption>
            </figure>
          </div>
        </section>

        <section id="features" className="border-t border-border py-[var(--section-gap)]" aria-labelledby="features-head">
          <div className="container">
            <div className="grid gap-6 lg:grid-cols-12 lg:items-end">
              <h2 id="features-head" className="section-head lg:col-span-6">
                What Doc-Hub does
              </h2>
              <p className="lead text-text-secondary lg:col-span-5 lg:col-start-8">
                Production-ready RAG infrastructure out of the box.
              </p>
            </div>
            <ul className="mt-14 border-b border-border">
              {features.map((f) => (
                <li key={f.title} className="grid gap-3 border-t border-border py-8 lg:grid-cols-12 lg:gap-8">
                  <h3 className="item-title lg:col-span-5">{f.title}</h3>
                  <p className="max-w-[60ch] text-[17px] leading-relaxed text-text-secondary lg:col-span-6 lg:col-start-7">{f.desc}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="pricing" className="bg-surface-2 py-[var(--section-gap)]" aria-labelledby="pricing-head">
          <div className="container">
            <div className="grid gap-6 lg:grid-cols-12 lg:items-end">
              <h2 id="pricing-head" className="section-head lg:col-span-6">
                Pricing
              </h2>
              <p className="lead text-text-secondary lg:col-span-5 lg:col-start-8">Scale as your knowledge base grows.</p>
            </div>
            <div className="stock sheet mt-14 rounded-xl px-5 sm:px-8">
              <table className="price-table w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-border text-sm text-muted">
                    <th scope="col" className="font-medium">Plan</th>
                    <th scope="col" className="font-medium">Price</th>
                    <th scope="col" className="font-medium">Tokens</th>
                    <th scope="col" className="font-medium">Storage</th>
                    <th scope="col" className="font-medium">Documents</th>
                    <th scope="col">
                      <span className="sr-only">Sign up</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {plans.map((p) => (
                    <tr key={p.name}>
                      <th scope="row" className="item-title font-semibold">
                        {p.name}
                        {p.highlight && (
                          <span className="ml-3 inline-block rounded-md border border-border-strong px-2 py-0.5 align-middle text-xs font-medium tracking-normal text-text-secondary">
                            Most popular
                          </span>
                        )}
                      </th>
                      <td className="text-right md:text-left">
                        <span className="text-[2.25rem] font-semibold leading-none tracking-[-0.04em]">{p.price}</span>
                        <span className="ml-0.5 text-muted">{p.period}</span>
                      </td>
                      <td data-label="Tokens" className="tabular-nums">{p.tokens}</td>
                      <td data-label="Storage" className="tabular-nums">{p.storage}</td>
                      <td data-label="Documents" className="tabular-nums">{p.docs}</td>
                      <td className="price-action md:text-right">
                        <a
                          href={p.planId === 'free' ? `${DASHBOARD_URL}/register` : `${DASHBOARD_URL}/register?plan=${p.planId}`}
                          className={`btn btn-sm w-full md:w-auto ${p.highlight ? 'btn-ink' : 'btn-card'}`}
                        >
                          {p.cta}
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="desk py-[var(--section-gap)]" aria-labelledby="close-head">
          <div className="container grid items-center gap-12 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-24">
            <div>
              <h2 id="close-head" className="section-head">
                Put an assistant on your site.
              </h2>
              <p className="lead mt-5 text-text-secondary">Get started in minutes. The free plan needs no card.</p>
              <a href={`${DASHBOARD_URL}/register`} className="btn btn-ink mt-8">
                Create your workspace
              </a>
            </div>
            <figure className="m-0 min-w-0">
              <div className="stock sheet rounded-lg p-6 sm:p-8">
                <EmbedSnippet />
              </div>
              <figcaption className="mt-3 text-sm text-muted">
                The embed code from your dashboard. A widget key can only answer questions, so it is safe to publish.
              </figcaption>
            </figure>
          </div>
        </section>
      </main>

      <footer className="border-t border-border py-16">
        <div className="container grid gap-10 md:grid-cols-12">
          <div className="md:col-span-6">
            <Wordmark className="text-[2.5rem] leading-none" />
          </div>
          <ul className="grid gap-3 text-[15px] md:col-span-3 md:col-start-10">
            <li><a href="#features" className="link">Features</a></li>
            <li><a href="#pricing" className="link">Pricing</a></li>
            <li><a href={`${DASHBOARD_URL}/login`} className="link">Sign in</a></li>
          </ul>
          <p className="text-sm text-muted md:col-span-12">&copy; {new Date().getFullYear()} Doc-Hub. All rights reserved.</p>
        </div>
      </footer>
    </>
  )
}
