import { describe, expect, it } from 'vitest'
import { buildSourceIndexMap, splitByCitations, stripCitations } from './markdown'

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
