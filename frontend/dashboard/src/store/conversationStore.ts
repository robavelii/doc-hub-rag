import { create } from 'zustand'
import type { ConversationSummary } from '@shared/types'
import api from '../lib/api'

// The history list lives in the app sidebar while the thread lives in the Chat page,
// so both read the same list from here.
interface ConversationState {
  conversations: ConversationSummary[]
  status: 'idle' | 'loading' | 'ready' | 'error'
  load: () => Promise<void>
  remove: (id: string) => Promise<void>
}

export const useConversationStore = create<ConversationState>((set) => ({
  conversations: [],
  status: 'idle',

  load: async () => {
    set((s) => ({ status: s.conversations.length ? s.status : 'loading' }))
    try {
      const { data } = await api.get<ConversationSummary[]>('/conversations')
      set({ conversations: data, status: 'ready' })
    } catch {
      set({ status: 'error' })
    }
  },

  remove: async (id) => {
    await api.delete(`/conversations/${id}`)
    set((s) => ({ conversations: s.conversations.filter((c) => c.id !== id) }))
  },
}))
