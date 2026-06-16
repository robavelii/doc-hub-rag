import { useEffect, useState } from 'react'
import { MessageSquarePlus, Search, Trash2 } from 'lucide-react'
import type { ConversationSummary } from '@shared/types'
import api from '../lib/api'
import { Button, EmptyState, Input, Skeleton, useToast } from './ui'
import { cn } from '../lib/cn'

interface Props {
  activeId: string | null
  onSelect: (id: string | null) => void
  onNew: () => void
}

export default function ConversationSidebar({ activeId, onSelect, onNew }: Props) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const { toast } = useToast()

  const load = async () => {
    try {
      const { data } = await api.get<ConversationSummary[]>('/conversations')
      setConversations(data)
    } catch {
      toast('error', 'Failed to load conversations')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const handleDelete = async (id: string) => {
    await api.delete(`/conversations/${id}`)
    setConversations((prev) => prev.filter((c) => c.id !== id))
    if (activeId === id) onSelect(null)
    toast('success', 'Conversation deleted')
  }

  const filtered = conversations.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="flex h-full w-64 shrink-0 flex-col border-r border-border-subtle max-md:absolute max-md:z-20 max-md:h-full max-md:bg-surface">
      <div className="p-3 border-b border-border-subtle">
        <Button onClick={onNew} className="w-full" size="sm">
          <MessageSquarePlus size={16} />
          New Chat
        </Button>
      </div>
      <div className="p-3">
        <Input
          placeholder="Search..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          icon={<Search size={14} />}
        />
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {loading ? (
          <div className="space-y-2 p-2">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState title="No conversations" description="Start a new chat to begin" />
        ) : (
          filtered.map((c) => (
            <div
              key={c.id}
              className={cn(
                'group flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition',
                activeId === c.id ? 'bg-primary-muted text-primary' : 'text-muted hover:bg-surface-2/50 hover:text-text'
              )}
            >
              <button type="button" onClick={() => onSelect(c.id)} className="truncate flex-1 text-left">
                {c.title}
              </button>
              <button
                type="button"
                onClick={() => void handleDelete(c.id)}
                className="opacity-0 group-hover:opacity-100 p-1 text-muted hover:text-danger"
                aria-label={`Delete conversation ${c.title}`}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
