import { describe, expect, it } from 'vitest'
import { buildSourceIndexMap, citationId, citationsToLinks, splitByCitations, stripCitations } from './markdown'

describe('splitByCitations', () => {
  it('splits text around citation markers', () => {
    const parts = splitByCitations('Hello [source:abc] world [source:def]!')
    expect(parts).toEqual([
      { type: 'text', value: 'Hello ' },
      { type: 'citation', chunkId: 'abc' },
      { type: 'text', value: ' world ' },
      { type: 'citation', chunkId: 'def' },
      { type: 'text', value: '!' },
    ])
  })

  it('returns single text part when no citations', () => {
    expect(splitByCitations('plain text')).toEqual([{ type: 'text', value: 'plain text' }])
  })
})

describe('buildSourceIndexMap', () => {
  it('assigns 1-based indices to unique source ids', () => {
    const map = buildSourceIndexMap([
      { id: 'a' },
      { id: 'b' },
      { id: 'a' },
    ])
    expect(map.get('a')).toBe(1)
    expect(map.get('b')).toBe(2)
  })
})

describe('stripCitations', () => {
  it('removes citation markers from content', () => {
    expect(stripCitations('Answer [source:abc] here')).toBe('Answer  here')
  })
})

describe('citationsToLinks', () => {
  it('rewrites markers to inline links that round-trip the chunk id', () => {
    const md = citationsToLinks('Leave is 25 days [source:c-1/x] per year.')
    expect(md).toBe('Leave is 25 days [cite](#cite-c-1%2Fx) per year.')
    expect(citationId('#cite-c-1%2Fx')).toBe('c-1/x')
  })

  it('ignores ordinary links', () => {
    expect(citationId('https://example.com')).toBeNull()
    expect(citationId(undefined)).toBeNull()
  })
})
