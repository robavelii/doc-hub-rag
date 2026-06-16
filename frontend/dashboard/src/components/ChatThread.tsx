import { useEffect, useRef, useState } from 'react'
import { Send, ThumbsDown, ThumbsUp } from 'lucide-react'
import type { ConversationMessage, QueryResultMetrics, QuerySource } from '@shared/types'
import MarkdownAnswer from './MarkdownAnswer'
import MessageActions from './MessageActions'
import QueryMetrics from './QueryMetrics'
import SourcesPanel from './SourcesPanel'
import { Avatar, Button, EmptyState, Textarea, useToast } from './ui'
import { streamQuery } from '../lib/stream'
import api from '../lib/api'
import { cn } from '../lib/cn'

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
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
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

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.length === 0 && (
          <EmptyState
            title="Start a conversation"
            description="Ask questions about your uploaded documents and get cited answers."
            action={<Button onClick={() => void sendMessage(SUGGESTED_PROMPTS[0])}>Try a sample question</Button>}
          />
        )}

        {messages.map((msg, i) => (
          <div key={i} className={cn('flex gap-3', msg.role === 'user' ? 'flex-row-reverse' : '')}>
            <Avatar name={msg.role === 'user' ? 'You' : 'AI'} size="sm" />
            <div className={cn('max-w-[80%]', msg.role === 'user' ? 'items-end' : '')}>
              <div
                className={cn(
                  'rounded-2xl px-4 py-3',
                  msg.role === 'user'
                    ? 'bg-primary/15 border border-primary/30'
                    : 'glass border border-glass-border'
                )}
              >
                {msg.role === 'assistant' ? (
                  <>
                    <MarkdownAnswer content={msg.content} sources={msg.sources} />
                    {msg.streaming && (
                      <span className="inline-flex gap-1 ml-1">
                        <span className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce" />
                        <span className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0.1s' }} />
                        <span className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0.2s' }} />
                      </span>
                    )}
                    {!msg.streaming && msg.content && (
                      <>
                        <MessageActions question={messages[i - 1]?.content} answer={msg.content} sources={msg.sources} />
                        {msg.sources && msg.sources.length > 0 && <SourcesPanel sources={msg.sources} />}
                        {msg.metrics && <QueryMetrics metrics={msg.metrics} />}
                        {msg.query_log_id && (
                          <div className="flex gap-1 mt-2 pt-2 border-t border-border-subtle">
                            <button type="button" aria-label="Helpful answer" onClick={() => void submitFeedback(msg.query_log_id!, 1)} className="p-1.5 rounded-md text-muted hover:text-success">
                              <ThumbsUp size={14} />
                            </button>
                            <button type="button" aria-label="Unhelpful answer" onClick={() => void submitFeedback(msg.query_log_id!, -1)} className="p-1.5 rounded-md text-muted hover:text-danger">
                              <ThumbsDown size={14} />
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </>
                ) : (
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                )}
              </div>
              {msg.created_at && (
                <p className="text-[10px] text-muted mt-1 px-1">
                  {new Date(msg.created_at).toLocaleTimeString()}
                </p>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="flex gap-2 mt-4 pt-4 border-t border-border">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void sendMessage()
            }
          }}
          placeholder="Ask a question…"
          rows={2}
          className="flex-1 resize-none"
          disabled={loading}
        />
        <Button onClick={() => void sendMessage()} disabled={loading || !input.trim()} className="self-end">
          <Send size={18} />
        </Button>
      </div>
    </div>
  )
}
