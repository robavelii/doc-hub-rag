import { useState } from 'react'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { ChatMessage, StreamEvent } from '@shared/types'

interface WidgetProps {
  apiKey: string
  primaryColor: string
  apiBase: string
  welcomeMessage?: string
  position?: string
  tenantName?: string
}

interface DisplayMessage extends ChatMessage {
  streaming?: boolean
}

export default function Widget({
  apiKey,
  primaryColor,
  apiBase,
  welcomeMessage = 'Hi! How can I help you today?',
  position = 'bottom-right',
  tenantName = 'Assistant',
}: WidgetProps) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [welcomed, setWelcomed] = useState(false)

  const openChat = () => {
    setOpen(true)
    if (!welcomed) {
      setMessages([{ role: 'assistant', content: welcomeMessage }])
      setWelcomed(true)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || loading) return
    const question = input
    setInput('')
    setLoading(true)
    setMessages((prev) => [...prev, { role: 'user', content: question }])
    setMessages((prev) => [...prev, { role: 'assistant', content: '', streaming: true }])

    let fullContent = ''
    try {
      await fetchEventSource(`${apiBase.replace(/\/$/, '')}/query/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey,
        },
        body: JSON.stringify({ question }),
        onmessage(event) {
          if (!event.data) return
          const data = JSON.parse(event.data) as StreamEvent
          if (data.type === 'chunk') {
            fullContent += data.content
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last) {
                updated[updated.length - 1] = { role: 'assistant', content: fullContent, streaming: true }
              }
              return updated
            })
          }
          if (data.type === 'done') {
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last) {
                updated[updated.length - 1] = { role: 'assistant', content: fullContent, streaming: false }
              }
              return updated
            })
            setLoading(false)
          }
        },
        onerror() {
          setLoading(false)
        },
      })
    } catch {
      setLoading(false)
    }
  }

  const positionClass = position === 'bottom-left' ? 'rag-widget-left' : 'rag-widget-right'
  const themeVars = { '--rag-accent': primaryColor, '--rag-on-accent': readableOn(primaryColor) } as React.CSSProperties

  return (
    <div className={`rag-widget ${positionClass}`} style={themeVars}>
      {!open && (
        <button type="button" className="rag-widget-toggle" onClick={openChat} aria-label="Open chat">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" />
          </svg>
        </button>
      )}
      {open && (
        <section className="rag-widget-panel" role="dialog" aria-label={`Chat with ${tenantName}`}>
          <header className="rag-widget-header">
            <span className="rag-widget-mark" aria-hidden="true" />
            <h2 className="rag-widget-title">{tenantName}</h2>
            <button type="button" className="rag-icon-btn" onClick={() => setOpen(false)} aria-label="Close chat">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </header>
          <ol className="rag-widget-messages" aria-live="polite">
            {messages.map((m, i) => {
              const text = stripCitations(m.content)
              return (
                <li key={i} className={`rag-msg ${m.role}`}>
                  {m.streaming && !text ? (
                    <span className="rag-msg-status">Searching</span>
                  ) : (
                    text
                  )}
                  {m.streaming && <span className="rag-caret" aria-hidden="true" />}
                </li>
              )
            })}
          </ol>
          <form
            className="rag-widget-input"
            onSubmit={(e) => {
              e.preventDefault()
              void sendMessage()
            }}
          >
            <label htmlFor="rag-input" className="rag-sr">
              Message
            </label>
            <input id="rag-input" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask a question…" autoComplete="off" />
            <button type="submit" className="rag-send" disabled={loading || !input.trim()} aria-label="Send">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 19V5M5 12l7-7 7 7" />
              </svg>
            </button>
          </form>
        </section>
      )}
    </div>
  )
}

// The server marks citations as [source:<chunk_id>]; the public widget shows the answer without them.
// A marker still being streamed ("[sour…") is held back until it closes.
export function stripCitations(content: string): string {
  return content
    .replace(/\s?\[source:[^\]]*\]/g, '')
    .replace(/\s?\[(s(o(u(r(c(e(:[^\]]*)?)?)?)?)?)?)?$/, '')
}

// Ink or white on the tenant's colour, whichever reads better
export function readableOn(hex: string): string {
  const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex.trim())
  if (!m || !m[1]) return 'var(--rag-white)'
  const h = m[1].length === 3 ? m[1].replace(/./g, (c) => c + c) : m[1]
  const [r, g, b] = [0, 2, 4].map((i) => {
    const v = parseInt(h.slice(i, i + 2), 16) / 255
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  }) as [number, number, number]
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
  return lum > 0.4 ? 'var(--rag-ink)' : 'var(--rag-white)'
}
