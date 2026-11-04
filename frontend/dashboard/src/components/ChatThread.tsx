import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowUp, ThumbsDown, ThumbsUp } from 'lucide-react'
import type { ConversationMessage, QueryResultMetrics, QuerySource } from '@shared/types'
import MarkdownAnswer from './MarkdownAnswer'
import MessageActions from './MessageActions'
import QueryMetrics from './QueryMetrics'
import SourcesPanel from './SourcesPanel'
import { IconButton, useToast } from './ui'
import { streamQuery } from '../lib/stream'
import api from '../lib/api'

interface DisplayMessage {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  sources?: QuerySource[]
  metrics?: QueryResultMetrics
  query_log_id?: string
  created_at?: string
}

const SUGGESTED_PROMPTS = [
  'What is in my knowledge base?',
  'Summarize the main topics',
  'What are the key findings?',
]

interface Props {
  conversationId: string | null
  initialMessages?: ConversationMessage[]
  onConversationCreated?: (id: string) => void
}

function formatTime(iso?: string) {
  return iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : null
}

interface ComposerProps {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  busy: boolean
  autoFocus?: boolean
}

function Composer({ value, onChange, onSubmit, busy, autoFocus }: ComposerProps) {
  const ref = useRef<HTMLTextAreaElement>(null)

  // Grow with the text up to about eight lines, then scroll
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 208)}px`
  }, [value])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    onSubmit()
  }

  return (
    <form
      onSubmit={submit}
      className="rounded-3xl border border-field bg-surface shadow-md transition-[border-color] duration-micro focus-within:border-muted"
    >
      <label htmlFor="chat-input" className="sr-only">
        Ask a question
      </label>
      <textarea
        id="chat-input"
        ref={ref}
        rows={1}
        autoFocus={autoFocus}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            onSubmit()
          }
        }}
        placeholder="Ask a question…"
        className="block max-h-52 w-full resize-none bg-transparent px-5 pb-1 pt-4 text-[15px] leading-relaxed text-text placeholder:text-muted focus-visible:outline-none"
      />
      <div className="flex items-center justify-end px-3 pb-3">
        <button
          type="submit"
          disabled={busy || !value.trim()}
          aria-label="Send"
          className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-fg transition-[background-color,transform] duration-micro hover:bg-primary-hover active:translate-y-px disabled:cursor-not-allowed disabled:bg-surface-3 disabled:text-muted"
        >
          <ArrowUp size={18} strokeWidth={2.25} />
        </button>
      </div>
    </form>
  )
}

export default function ChatThread({ conversationId, initialMessages = [], onConversationCreated }: Props) {
  const [messages, setMessages] = useState<DisplayMessage[]>(
    initialMessages.map((m) => ({
      role: m.role as 'user' | 'assistant',
      content: m.content,
      sources: m.sources,
      metrics: m.metrics,
      query_log_id: m.query_log_id ?? undefined,
      created_at: m.created_at ?? undefined,
    }))
  )
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [activeConvoId, setActiveConvoId] = useState(conversationId)
  const bottomRef = useRef<HTMLDivElement>(null)
  const { toast } = useToast()

  useEffect(() => {
    setActiveConvoId(conversationId)
  }, [conversationId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  const sendMessage = async (text?: string) => {
    const question = (text ?? input).trim()
    if (!question || loading) return
    setInput('')
    setLoading(true)
    const now = new Date().toISOString()
    setMessages((prev) => [...prev, { role: 'user', content: question, created_at: now }])
    setMessages((prev) => [...prev, { role: 'assistant', content: '', streaming: true }])

    let fullContent = ''
    try {
      await streamQuery(
        question,
        activeConvoId,
        (data) => {
          if (data.type === 'chunk') {
            fullContent += data.content
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last) updated[updated.length - 1] = { role: 'assistant', content: fullContent, streaming: true }
              return updated
            })
          }
          if (data.type === 'done') {
            if (data.conversation_id && !activeConvoId) {
              setActiveConvoId(data.conversation_id)
              onConversationCreated?.(data.conversation_id)
            }
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last) {
                updated[updated.length - 1] = {
                  role: 'assistant',
                  content: fullContent,
                  streaming: false,
                  sources: data.sources,
                  query_log_id: data.query_log_id,
                  created_at: new Date().toISOString(),
                  metrics: {
                    confidence: data.confidence,
                    confidence_tier: data.confidence_tier,
                    sources: data.sources,
                    tokens_total: data.tokens_total,
                    latency_ms: data.latency_ms,
                    from_cache: data.from_cache,
                    provider: data.provider,
                    model: data.model,
                    query_log_id: data.query_log_id,
                  },
                }
              }
              return updated
            })
            setLoading(false)
          }
        },
        () => {
          setLoading(false)
          toast('error', 'Query failed', 'Please try again')
        }
      )
    } catch {
      setLoading(false)
    }
  }

  const submitFeedback = async (queryLogId: string, rating: number) => {
    await api.post('/feedback', { query_log_id: queryLogId, rating })
    toast('success', rating === 1 ? 'Thanks for the feedback!' : 'Feedback recorded')
  }

  if (messages.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4 pb-[12vh]">
        <div className="w-full max-w-2xl">
          <h2 className="text-center text-[28px] font-semibold leading-tight tracking-tight text-text">Start a conversation</h2>
          <p className="mb-7 mt-2 text-center text-[15px] text-muted">
            Ask questions about your uploaded documents and get cited answers.
          </p>
          <Composer value={input} onChange={setInput} onSubmit={() => void sendMessage()} busy={loading} autoFocus />
          <ul className="mt-5 grid gap-1" aria-label="Suggested questions">
            {SUGGESTED_PROMPTS.map((p) => (
              <li key={p}>
                <button
                  type="button"
                  onClick={() => void sendMessage(p)}
                  className="w-full rounded-xl px-4 py-2.5 text-left text-sm text-text-secondary transition-colors duration-micro hover:bg-primary-muted hover:text-text"
                >
                  {p}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <ol className="mx-auto w-full max-w-3xl space-y-8 px-4 pb-8 pt-4" aria-label="Conversation">
          {messages.map((msg, i) =>
            msg.role === 'user' ? (
              <li key={i} className="flex flex-col items-end">
                <div className="max-w-[85%] whitespace-pre-wrap rounded-3xl bg-surface-3 px-4 py-2.5 text-[15px] leading-relaxed text-text">
                  {msg.content}
                </div>
                {msg.created_at && <time className="mt-1 px-2 text-xs text-muted">{formatTime(msg.created_at)}</time>}
              </li>
            ) : (
              <li key={i} className="group">
                <div className="mb-1.5 flex items-baseline gap-2 text-sm">
                  <span className="font-semibold text-text">Doc-Hub</span>
                  {msg.created_at && <time className="text-xs text-muted">{formatTime(msg.created_at)}</time>}
                </div>

                {msg.streaming && !msg.content ? (
                  <p className="text-[15px] text-muted" role="status">
                    Searching your documents
                    <span className="ml-1 inline-block h-4 w-0.5 translate-y-0.5 bg-muted animate-caret" aria-hidden="true" />
                  </p>
                ) : (
                  <MarkdownAnswer content={msg.content} sources={msg.sources} />
                )}
                {msg.streaming && msg.content && (
                  <span className="inline-block h-4 w-0.5 translate-y-0.5 bg-text animate-caret" aria-hidden="true" />
                )}

                {!msg.streaming && msg.content && (
                  <>
                    {msg.sources && msg.sources.length > 0 && <SourcesPanel sources={msg.sources} />}
                    <div className="mt-2 flex flex-wrap items-center gap-0.5 text-muted">
                      <MessageActions question={messages[i - 1]?.content} answer={msg.content} sources={msg.sources} />
                      {msg.query_log_id && (
                        <>
                          <IconButton label="Helpful answer" onClick={() => void submitFeedback(msg.query_log_id!, 1)} className="hover:text-success">
                            <ThumbsUp size={14} />
                          </IconButton>
                          <IconButton label="Unhelpful answer" onClick={() => void submitFeedback(msg.query_log_id!, -1)} className="hover:text-danger">
                            <ThumbsDown size={14} />
                          </IconButton>
                        </>
                      )}
                    </div>
                    {msg.metrics && <QueryMetrics metrics={msg.metrics} />}
                  </>
                )}
              </li>
            )
          )}
        </ol>
        <div ref={bottomRef} />
      </div>

      <div className="shrink-0 px-4 pb-4">
        <div className="mx-auto w-full max-w-3xl">
          <Composer value={input} onChange={setInput} onSubmit={() => void sendMessage()} busy={loading} />
        </div>
      </div>
    </div>
  )
}
