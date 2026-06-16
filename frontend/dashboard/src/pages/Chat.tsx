import { useCallback, useState } from 'react'
import type { ConversationDetail } from '@shared/types'
import api from '../lib/api'
import ChatThread from '../components/ChatThread'
import ConversationSidebar from '../components/ConversationSidebar'

export default function Chat() {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [initialMessages, setInitialMessages] = useState<ConversationDetail['messages']>([])
  const [threadKey, setThreadKey] = useState(0)

  const handleSelect = useCallback(async (id: string | null) => {
    setConversationId(id)
    if (!id) {
      setInitialMessages([])
      setThreadKey((k) => k + 1)
      return
    }
    const { data } = await api.get<ConversationDetail>(`/conversations/${id}`)
    setInitialMessages(data.messages)
    setThreadKey((k) => k + 1)
  }, [])

  const handleNew = () => {
    setConversationId(null)
    setInitialMessages([])
    setThreadKey((k) => k + 1)
  }

  const handleConversationCreated = (id: string) => {
    setConversationId(id)
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] -m-4 lg:-m-6 rounded-xl overflow-hidden border border-border-subtle">
      <ConversationSidebar
        activeId={conversationId}
        onSelect={(id) => void handleSelect(id)}
        onNew={handleNew}
      />
      <div className="flex-1 p-4 lg:p-6 overflow-hidden">
        <ChatThread
          key={threadKey}
          conversationId={conversationId}
          initialMessages={initialMessages}
          onConversationCreated={handleConversationCreated}
        />
      </div>
    </div>
  )
}
