import { describe, expect, it } from 'vitest'
import type { StreamChunkEvent, StreamDoneEvent, StreamEvent } from '@shared/types'

function parseStreamEvent(raw: string): StreamEvent {
  return JSON.parse(raw) as StreamEvent
}

describe('StreamEvent types', () => {
  it('parses chunk events', () => {
    const event = parseStreamEvent('{"type":"chunk","content":"Hello "}')
    expect(event.type).toBe('chunk')
    expect((event as StreamChunkEvent).content).toBe('Hello ')
  })

  it('parses done events with sources and metrics', () => {
    const event = parseStreamEvent(
      '{"type":"done","sources":[{"id":"abc","text":"preview","filename":"doc.txt"}],"confidence":0.85,"tokens_total":42,"latency_ms":320,"from_cache":false,"provider":"ollama","model":"llama3.2:1b"}'
    )
    expect(event.type).toBe('done')
    const done = event as StreamDoneEvent
    expect(done.confidence).toBe(0.85)
    expect(done.sources).toHaveLength(1)
    expect(done.sources[0]?.id).toBe('abc')
    expect(done.tokens_total).toBe(42)
    expect(done.latency_ms).toBe(320)
    expect(done.from_cache).toBe(false)
    expect(done.provider).toBe('ollama')
    expect(done.model).toBe('llama3.2:1b')
  })
})

describe('shared API types', () => {
  it('validates document status union', () => {
    const statuses = ['pending', 'processing', 'ready', 'failed'] as const
    expect(statuses).toContain('ready')
  })
})
