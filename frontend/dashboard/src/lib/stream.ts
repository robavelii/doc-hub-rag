import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { StreamEvent } from '@shared/types'

export async function streamQuery(
  question: string,
  conversationId: string | null,
  onMessage: (event: StreamEvent) => void,
  onError?: (err: unknown) => void
): Promise<void> {
  const token = localStorage.getItem('access_token')
  await fetchEventSource('/api/query/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token ?? ''}`,
    },
    body: JSON.stringify({ question, conversation_id: conversationId }),
    onmessage(event) {
      if (event.data) {
        onMessage(JSON.parse(event.data) as StreamEvent)
      }
    },
    onerror(err) {
      onError?.(err)
      throw err
    },
  })
}
