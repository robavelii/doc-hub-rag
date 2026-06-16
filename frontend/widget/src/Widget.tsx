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

  return (
    <div className={`rag-widget ${positionClass}`} style={{ '--primary': primaryColor } as React.CSSProperties}>
      {!open && (
        <button
          className="rag-widget-toggle"
          onClick={openChat}
          style={{ background: primaryColor }}
          aria-label="Open chat"
        >
          Chat
        </button>
      )}
      {open && (
        <div className="rag-widget-panel">
          <div className="rag-widget-header" style={{ background: primaryColor }}>
            <span>{tenantName}</span>
            <button onClick={() => setOpen(false)} aria-label="Close chat">
              ×
            </button>
          </div>
          <div className="rag-widget-messages">
            {messages.map((m, i) => (
              <div key={i} className={`rag-msg ${m.role}`}>
                {m.content}
                {m.streaming && <span>▌</span>}
              </div>
            ))}
          </div>
          <div className="rag-widget-input">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void sendMessage()}
              placeholder="Ask a question..."
              aria-label="Message"
            />
            <button onClick={() => void sendMessage()} disabled={loading} style={{ background: primaryColor }} aria-label="Send">
              →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
