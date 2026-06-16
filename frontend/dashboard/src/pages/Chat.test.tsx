import { describe, expect, it } from 'vitest'
import { splitByCitations, stripCitations } from '../lib/markdown'

describe('ChatThread citation rendering helpers', () => {
  it('splits answer text by citation markers', () => {
    const parts = splitByCitations('Answer with source [source:abc-123] and more.')
    expect(parts.some((p) => p.type === 'citation')).toBe(true)
  })

  it('strips citations for plain preview', () => {
    const plain = stripCitations('Answer with source [source:abc-123] here.')
    expect(plain).not.toContain('[source:')
  })
})
