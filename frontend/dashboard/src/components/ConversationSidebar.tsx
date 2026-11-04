import { useEffect, useMemo, useState } from 'react'
import { NavLink, useMatch, useNavigate } from 'react-router-dom'
import { Search, Trash2 } from 'lucide-react'
import type { ConversationSummary } from '@shared/types'
import { useConversationStore } from '../store/conversationStore'
import { Skeleton, useToast } from './ui'
import { cn } from '../lib/cn'

interface Props {
  onNavigate?: () => void
}

const DAY = 24 * 60 * 60 * 1000

function groupLabel(iso: string | null | undefined, now: number): string {
  if (!iso) return 'Older'
  const age = now - new Date(iso).getTime()
  if (age < DAY) return 'Today'
  if (age < 2 * DAY) return 'Yesterday'
  if (age < 7 * DAY) return 'Previous 7 days'
  if (age < 30 * DAY) return 'Previous 30 days'
  return 'Older'
}

function groupConversations(list: ConversationSummary[]) {
  const now = Date.now()
  const groups: { label: string; items: ConversationSummary[] }[] = []
  for (const c of list) {
    const label = groupLabel(c.updated_at ?? c.created_at, now)
    const last = groups[groups.length - 1]
    if (last && last.label === label) last.items.push(c)
    else groups.push({ label, items: [c] })
  }
  return groups
}

export default function ConversationSidebar({ onNavigate }: Props) {
  const { conversations, status, load, remove } = useConversationStore()
  const [search, setSearch] = useState('')
  const conversationId = useMatch('/chat/:conversationId')?.params.conversationId
  const navigate = useNavigate()
  const { toast } = useToast()

  useEffect(() => {
    void load()
  }, [load])

  const handleDelete = async (c: ConversationSummary) => {
    try {
      await remove(c.id)
      if (conversationId === c.id) navigate('/chat')
      toast('success', 'Conversation deleted')
    } catch {
      toast('error', 'Could not delete the conversation')
    }
  }

  const groups = useMemo(
    () => groupConversations(conversations.filter((c) => c.title.toLowerCase().includes(search.toLowerCase()))),
    [conversations, search]
  )

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="px-2 pb-2">
        <label className="relative block">
          <span className="sr-only">Search conversations</span>
          <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search"
            className="h-8 w-full rounded-lg border border-transparent bg-transparent pl-8 pr-2 text-sm text-text placeholder:text-muted hover:bg-primary-muted focus:border-border focus:bg-surface"
          />
        </label>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {status === 'loading' && (
          <div className="space-y-2 px-2 pt-2" aria-label="Loading conversations">
            {[70, 55, 80, 60].map((w) => <Skeleton key={w} width={`${w}%`} height={14} />)}
          </div>
        )}

        {status === 'error' && (
          <div className="px-2 pt-2 text-sm text-muted">
            <p>Could not load your conversations.</p>
            <button type="button" onClick={() => void load()} className="mt-1 font-medium text-text underline underline-offset-2 hover:text-accent">
              Try again
            </button>
          </div>
        )}

        {status === 'ready' && groups.length === 0 && (
          <p className="px-2 pt-2 text-sm text-muted">
            {search ? 'No conversations match.' : 'Your conversations will appear here.'}
          </p>
        )}

        {groups.map((g) => (
          <section key={g.label} className="mt-3 first:mt-1">
            <h3 className="px-2 pb-1 text-xs font-medium text-muted">{g.label}</h3>
            <ul>
              {g.items.map((c) => (
                <li key={c.id} className="group relative">
                  <NavLink
                    to={`/chat/${c.id}`}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        'block truncate rounded-lg py-1.5 pl-2 pr-8 text-sm transition-colors duration-micro',
                        isActive ? 'bg-primary-muted font-medium text-text' : 'text-text-secondary hover:bg-primary-muted hover:text-text'
                      )
                    }
                  >
                    {c.title}
                  </NavLink>
                  <button
                    type="button"
                    onClick={() => void handleDelete(c)}
                    className="absolute right-1 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted opacity-0 transition-opacity duration-micro hover:text-danger focus-visible:opacity-100 group-hover:opacity-100"
                    aria-label={`Delete conversation ${c.title}`}
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  )
}
