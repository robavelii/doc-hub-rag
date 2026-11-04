import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { ConversationDetail } from '@shared/types'
import api from '../lib/api'
import ChatThread from '../components/ChatThread'
import { Button, Skeleton } from '../components/ui'
import { useConversationStore } from '../store/conversationStore'

interface ThreadState {
  key: string
  status: 'loading' | 'ready' | 'error'
  messages: ConversationDetail['messages']
}

export default function Chat() {
  const { conversationId } = useParams()
  const navigate = useNavigate()
  const reloadList = useConversationStore((s) => s.load)
  const [thread, setThread] = useState<ThreadState>({ key: 'new', status: 'ready', messages: [] })
  const [attempt, setAttempt] = useState(0)
  // Set when the open thread has just created this conversation, so the URL update
  // that follows does not reload (and remount) the thread mid-stream.
  const createdHere = useRef<string | null>(null)

  useEffect(() => {
    if (!conversationId) {
      setThread({ key: `new-${Date.now()}`, status: 'ready', messages: [] })
      return
    }
    if (createdHere.current === conversationId) {
      createdHere.current = null
      return
    }
    let cancelled = false
    setThread({ key: conversationId, status: 'loading', messages: [] })
    api
      .get<ConversationDetail>(`/conversations/${conversationId}`)
      .then(({ data }) => {
        if (!cancelled) setThread({ key: conversationId, status: 'ready', messages: data.messages })
      })
      .catch(() => {
        if (!cancelled) setThread({ key: conversationId, status: 'error', messages: [] })
      })
    return () => {
      cancelled = true
    }
  }, [conversationId, attempt])

  const handleConversationCreated = (id: string) => {
    createdHere.current = id
    void reloadList()
    navigate(`/chat/${id}`, { replace: true })
  }

  if (thread.status === 'loading') {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-8 px-4 pt-4" aria-label="Loading conversation">
        <Skeleton width="45%" height={36} className="ml-auto rounded-3xl" />
        <div className="space-y-2.5">
          <Skeleton width="20%" />
          <Skeleton width="95%" />
          <Skeleton width="88%" />
          <Skeleton width="60%" />
        </div>
      </div>
    )
  }

  if (thread.status === 'error') {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 text-center">
        <p className="text-[15px] text-text">This conversation could not be loaded.</p>
        <p className="text-sm text-muted">It may have been deleted, or the server is unreachable.</p>
        <div className="mt-2 flex gap-2">
          <Button variant="secondary" onClick={() => setAttempt((n) => n + 1)}>
            Try again
          </Button>
          <Button onClick={() => navigate('/chat')}>New chat</Button>
        </div>
      </div>
    )
  }

  return (
    <ChatThread
      key={thread.key}
      conversationId={conversationId ?? null}
      initialMessages={thread.messages}
      onConversationCreated={handleConversationCreated}
    />
  )
}
